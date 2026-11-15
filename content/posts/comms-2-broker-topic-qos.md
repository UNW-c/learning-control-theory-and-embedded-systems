---
title: "嵌入式通信（二）：broker、topic 与 QoS"
slug: "comms-2-broker-topic-qos"
date: 2026-11-15
lastmod: 2026-11-15
description: "broker 记什么、topic 怎么分层、QoS 三档怎么选，末尾一个完整的客户端。"
weight: 7
categories:
    - "嵌入式开发"
tags:
    - "MQTT"
    - "broker"
    - "QoS"
    - "遗嘱"
---

## 从设计原则出发

MQTT 本质上是给低功耗设备用的，让这种设备在信号差、链路经常断、还躲在 NAT 后面的环境里，仍然能把数据送到终端。这类设备一般是电池供电、算力和内存都很紧，可能连着一个不太稳的 4G 或者 NB-IoT，还得时不时睡一觉省电。嵌入式这边用到它的场合，多半是设备装在机器上或者摆在现场，状态要往手机、上位机或者服务器上报，参数也要能从外面改。

为了适应这些前提，MQTT 在 pub/sub 之外还带了 broker、topic、QoS、遗嘱、保留、会话这几样东西。

## 关于 broker

broker 承担一个中转站的身份，发布方和订阅方都只跟它建连接，彼此不直接连。broker 里维护一张订阅表，里面是每个客户端订了哪些 topic，收到报文以后按 topic 查这张表，查到几份就转发几份。

路由、会话、重发这些也都落在 broker 上，设备端只要维持一条 TCP 连接、按格式收发报文，带宽和内存都省在设备这一侧。broker 一般放在一台常开的机器或者云上，本机跑一个 mosquitto 拿来调试也很常见，PC 上开一个 `mosquitto_sub -t 'sensor/#' -v` 挂着，另一边用 `mosquitto_pub` 往里发，topic 通不通不用写代码就能验。

设备躲在 NAT 后面，映射表过一段时间就会过期，所以要靠心跳保活。keepalive 设成三十秒的话，这三十秒里没有其他报文来往，客户端就发一个 PINGREQ，broker 回一个 PINGRESP，一来一回说明链路还通，NAT 那边的映射也跟着续上。一个半 keepalive 时间里 broker 一个报文都没收到，就把这个连接摘掉。对端掉电、拔网线这种已经不在的情况，本地不主动发东西是发现不了的，只能靠这套超时。

休眠的设备睡了就没心跳，broker 那边按掉线处理，省电和在线这两个要求得自己权衡。

## 关于 topic

有 broker 之后，怎么把数据分给不同的接收方又成了问题，全用同一个主题名的话所有订阅者都收到所有数据，设备端还得自己筛一遍。所以 topic 分了层：用 `/` 隔开，订阅的时候 `+` 匹配一层，`#` 匹配剩下所有层，一条数据发一次就够了，谁要哪一层就订哪一层。

```
rm/2026/infantry/gimbal/angle
cmd/esp32-01/led
sensor/+/temp
sensor/#
```

`#` 只能放在最后，前面得有 `/`，写成 `sensor#` 不算通配。`$` 开头的是 broker 自己的主题，普通订阅收不到。这些规则对应的是一棵按 `/` 分层的前缀树，匹配的开销跟层数有关，跟订阅者有多少关系不大。名字是大小写敏感的，大小写混着写很容易订不上；中文能不能用要看 broker，就算能跑，日志和命令行工具显示出来也是乱的。

命名习惯上一般是项目、年份、兵种、模块、量这样往下排，分层有用的地方就在这里，订阅的时候可以只订某一个模块，也可以订整个兵种。

和 ROS 的 topic 也是同一个思路，区别是 ROS 有类型、MQTT 没有，两端靠约定。可以订得很粗，也可以订得很细，同一份数据在不同层上被不同的模块取用。

## 关于 QoS

QoS 解决的是发送速率和稳定性之间的取舍。发一次不管到没到是 0 级，适合姿态、温度这种下一拍还有的数据，丢一帧不影响后一帧；保证到但可能重复是 1 级，适合指令这一类，接收方按 id 去重；用四次交互换不重不漏是 2 级，最慢，适合配置下发这种不能重复执行的动作。

1 级会重复，是因为 PUBACK 在路上丢了，发布方没有收到确认，就按超时重发了一遍，实际上对面已经收到了。所以用 1 级的场景，接收方得能认出重复的那条，最简单的办法是每条消息带一个递增的 id，收到重复的直接丢掉。

2 级多两次交互，broker 还要给每个客户端存一份流程状态，知道这次交互走到哪一步，设备一多内存占用就明显。设备端内存本来就紧，常用的还是 0 和 1，不能重复的动作放到应用层做幂等。

QoS 只在客户端和 broker 之间保证，broker 往订阅者转发的时候按订阅时协商的级别走，实际生效的是发布和订阅里小的那个。发布端写 2、订阅端订的 0，整条链路还是按 0 走。

## 关于遗嘱、保留、会话

这几样在代码里就是几个字段。

```c
MQTTClient_willOptions will = MQTTClient_willOptions_initializer;
will.topicName   = "dev/esp32-01/status";   /* 遗嘱：异常断线由 broker 代发 */
will.message     = "offline";
will.qos         = 1;
will.retained    = 1;
opts.will        = &will;

opts.cleansession = 0;                      /* 会话：记住订阅和未确认的消息 */
```

```c
/* 保留：置位以后 broker 留最后一条，新订阅的人一上来就能拿到 */
MQTTClient_message online = MQTTClient_message_initializer;
online.payload    = "online";
online.payloadlen = 6;
online.retained   = 1;
MQTTClient_publishMessage(client, "dev/esp32-01/status", &online, &token);
```

保留和遗嘱经常挂在同一个 topic 上，上线发 online，掉线由 broker 发 offline，订阅这个 topic 的一端看到的就是设备当前的状态。

会话设 0 的时候，断线期间发过去的消息会在重连之后补推，补过来的东西可能已经过期，设备重启以后照着几分钟前的指令执行一遍会出事，所以指令里得带时间戳或者序号，超时的不执行。

## 一个完整的例子

一个设备端从连上到退出，把这些东西串起来大概是这样。

```c
static void publish(MQTTClient c, const char *topic, const char *data,
                    int len, int qos, int retain)
{
    MQTTClient_message m = MQTTClient_message_initializer;
    m.payload    = (void *)data;
    m.payloadlen = len;
    m.qos        = qos;
    m.retained   = retain;
    MQTTClient_publishMessage(c, topic, &m, NULL);
}

static void mqtt_task(void *arg)
{
    MQTTClient client;
    MQTTClient_create(&client, "tcp://192.168.1.10:1883", "esp32-01",
                      MQTTCLIENT_PERSISTENCE_NONE, NULL);
    MQTTClient_setCallbacks(client, NULL, on_lost, on_message, NULL);

    MQTTClient_connectOptions opts = MQTTClient_connectOptions_initializer;
    opts.keepAliveInterval = 30;
    opts.cleansession      = 0;

    MQTTClient_willOptions will = MQTTClient_willOptions_initializer;
    will.topicName = "dev/esp32-01/status";
    will.message   = "offline";
    will.qos       = 1;
    will.retained  = 1;
    opts.will      = &will;

    MQTTClient_connect(client, &opts);
    MQTTClient_subscribe(client, "cmd/esp32-01/#", 1);

    publish(client, "dev/esp32-01/status", "online", 6, 1, 1);

    while (running) {
        char buf[16];
        int len = snprintf(buf, sizeof(buf), "%.1f", read_temp());
        publish(client, "dev/esp32-01/telemetry", buf, len, 0, 0);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }

    MQTTClient_disconnect(client, 1000);
    MQTTClient_destroy(&client);
}
```

指令那一路走回调，按 topic 后面的层级看出是哪条指令，按 id 去重之后执行，执行完往 `dev/esp32-01/ack` 回一条带同一个 id 的消息。掉线的处理在 `on_lost` 里，`cleansession` 是 0 的话订阅关系还在，重连之后不需要重新订一遍，重连间隔按 1s、2s、4s 退避，避免断网期间反复重连。
