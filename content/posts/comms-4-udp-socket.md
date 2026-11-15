---
title: "嵌入式通信（四）：UDP 与 socket"
slug: "comms-4-udp-socket"
date: 2026-11-15
lastmod: 2026-11-15
description: "UDP 的数据报和广播，socket 的调用，还有 Linux 下的 SocketCAN。"
weight: 9
categories:
    - "嵌入式开发"
tags:
    - "UDP"
    - "socket"
    - "SocketCAN"
---

## UDP

UDP 是用户数据报协议，和 TCP 一起构成传输层的两种选择。TCP 有的连接、重传、按序交付，它一样都没有，头部也只有 8 个字节。

头部就四个字段，源端口、目的端口、长度、校验和各两个字节，剩下的都是数据。IPv4 下校验和可以填 0 表示不校验，接收端也就不验。

数据是一条一条发的，一次 sendto 对应一次 recvfrom，数据报的边界保留下来，所以没有 TCP 那种粘包问题，收到的要么是一整条，要么没有。一个数据报超过 MTU 会分片，以太网 MTU 是 1500，减掉 IP 头和 UDP 头，载荷一般控制在 1472 字节以内，丢一片整个报文就没了。

不用先建连接，第一个数据报发出去的时候中间没有握手，一问一答的短事务用它延迟低，DNS 查一条记录就是一个来回。

还有广播和组播，这是 TCP 做不到的。发送端把目的地址填成 `255.255.255.255` 或者子网广播地址，同一网段里的设备都能收到，接收端 bind 到 `INADDR_ANY` 上就能收，不用知道发送方的地址；组播是发送端填一个组播地址，接收端 join 到这个组，适合一对多的状态发布。

适合它的是丢一条不影响的数据，姿态、摇杆这类要的是当前值，丢一包就是图上少一个点，等着重传反而更慢。参数下发和文件不适合，真要在 UDP 上保证，就得在应用层加序号、CRC、ACK 和重传，写到后面越来越像 TCP。

```c
int fd = socket(AF_INET, SOCK_DGRAM, 0);
bind(fd, (struct sockaddr *)&addr, sizeof(addr));    /* 收的一方要 bind 端口 */
sendto(fd, data, len, 0, (struct sockaddr *)&to, sizeof(to));
recvfrom(fd, buf, sizeof(buf), 0, NULL, NULL);
```

嵌入式里常见的组合是控制指令走 TCP 或者 MQTT，姿态和高频遥测用 UDP 广播给上位机，局域网里广播一次所有设备都能收到。

## socket

socket 是操作系统给网络编程提供的一套接口，最早在 BSD Unix 上用，后来进了 POSIX，成了事实上的标准，Windows 那边有自己的实现，用法基本一样。它不绑定哪一种协议，创建的时候三个参数决定：地址族、套接字类型、协议号。常用的组合是 `AF_INET` 加 `SOCK_STREAM` 走 TCP，`AF_INET` 加 `SOCK_DGRAM` 走 UDP，`AF_UNIX` 加 `SOCK_STREAM` 是本机进程之间的 Unix domain socket。

一套接口覆盖了建连、收发、关闭这几件事：

```
socket()          创建，返回一个文件描述符
bind()            绑定本地地址和端口
listen()          服务端进入监听
accept()          取出一个已经建好的连接
connect()         客户端发起连接
send() / recv()   在已连接的套接字上收发
sendto() / recvfrom()   无连接的收发，UDP 用
setsockopt()      设置选项
close()           关闭
```

用它就不用自己写三次握手和四次挥手，`connect` 里把握手做了，`close` 里把挥手做了。

```c
/* 板子这边等 PC 连上来 */
int fd = socket(AF_INET, SOCK_STREAM, 0);
bind(fd, (struct sockaddr *)&addr, sizeof(addr));   /* addr 里填端口 8888 */
listen(fd, 4);

int c = accept(fd, NULL, NULL);                     /* 没有连接就阻塞在这 */
while (1) {
    int n = recv(c, buf, sizeof(buf), 0);
    if (n <= 0) break;                              /* 0 是对端关了 */
    feed(buf, n);                                   /* 交给解帧 */
    send(c, ack, ack_len, 0);
}
```

```c
/* PC 这边连板子 */
int fd = socket(AF_INET, SOCK_STREAM, 0);
connect(fd, (struct sockaddr *)&addr, sizeof(addr));
send(fd, frame, frame_len, 0);
recv(fd, buf, sizeof(buf), 0);
close(fd);
```

`setsockopt` 里有几个常调的：`SO_RCVTIMEO` 设接收超时，不设的话对端不发数据任务就一直卡在 recv 上；`TCP_NODELAY` 关掉 Nagle，小包频繁发的时候延迟能差几十毫秒；`SO_REUSEADDR` 让程序重启之后马上能 bind，不用等 TIME_WAIT 过去。

Linux 下 CAN 也是走 socket 的，地址族用 `PF_CAN`，类型 `SOCK_RAW`，协议 `CAN_RAW`，bind 的时候给一个接口索引，之后收发的是 `struct can_frame`，里面有 `can_id`、`can_dlc` 和最多八个字节的 `data`。这样 CAN 帧和网络报文一样是个文件描述符，能丢进 select 或者 epoll 一起等，不用给 CAN 单独开一套线程；can-utils 里的 candump、cansend 用的也是这个。

```c
int fd = socket(PF_CAN, SOCK_RAW, CAN_RAW);

struct sockaddr_can addr = {0};
struct ifreq ifr = {0};
strcpy(ifr.ifr_name, "can0");
ioctl(fd, SIOCGIFINDEX, &ifr);           /* 取 can0 的接口索引 */
addr.can_family  = AF_CAN;
addr.can_ifindex = ifr.ifr_ifindex;
bind(fd, (struct sockaddr *)&addr, sizeof(addr));

struct can_frame frame = { .can_id = 0x201, .can_dlc = 8 };
memcpy(frame.data, buf, 8);
write(fd, &frame, sizeof(frame));
```

`can_dlc` 是这一帧的数据长度，0 到 8，经典 CAN 一帧最多八个字节，CAN FD 换 `canfd_frame` 最多六十四。

换平台的时候写法不用换。Linux 上是内核的 socket，板子上是 lwIP 的 socket，裸机和 RTOS 都能跑，函数名和返回值的语义一样，PC 上验过的收发逻辑搬过去改改地址就能用。区别在内存，lwIP 里每个连接是一个 PCB，静态分配或者从内存池里取，连接数开不了太多，`setsockopt` 也不是全都支持，用之前得看一下手上这个版本实现了哪些。

嵌入式开发要学这些通信方式，尤其是 MQTT。它用在边缘嵌入式设备和终端设备的通信上，和嵌入式开发关系紧密，但它本身还是网络通信协议，和 TCP 一样。
