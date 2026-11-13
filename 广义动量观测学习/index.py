"""广义动量观测：一维刚体仿真 + 实时调参可视化。

原伪代码对应关系（约简形式）:
  r_k = r_{k-1} + k * (p_k - p_{k-1} - f*dt - r_{k-1}*dt)

默认实现使用等价的影子动量形式（数值更稳）:
  p_hat += dt * (f + r)
  e = p - p_hat
  r = k * e

运行:
  python index.py
"""

from app.main import main


if __name__ == "__main__":
    main()
