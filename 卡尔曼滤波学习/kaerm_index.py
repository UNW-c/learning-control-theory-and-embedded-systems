"""光流与加速度计融合卡尔曼滤波：数据生成 + 实时 Q/R 调参可视化。

原始伪代码对应关系:
  状态 x = [v, b]
  控制量 u = a_mea (加速度计)
  观测量 z = v_mea (光流)
  预测: x = F x + B u
  更新: x = x + K (z - H x)

运行:
  python kaerm_index.py
"""

from app.main import main


if __name__ == "__main__":
    main()