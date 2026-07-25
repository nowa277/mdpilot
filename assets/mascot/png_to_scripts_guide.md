工具已就绪。

png_to_script.py — 位于 assets/mascot/png_to_script.py

用法：
python png_to_script.py 你画的.png [输出脚本.py]


工作流：

1. 打开 Lospec（https://lospec.com/pixel-editor/）或 Piskel（https://www.piskelapp.com/）
2. 新建画布（建议 32×32 或 36×36）
3. 手动绘制你想要的吉祥物
4. 导出 PNG（带透明背景）
5. 把 PNG 放到 assets/mascot/ 目录
6. 运行 python png_to_script.py xxx.png xxx_script.py
7. 得到的 .py 脚本可直接 python xxx_script.py 运行，输出 512×512 像素画

工具会自动检测：画布尺寸、颜色数量、是否左右对称，并生成带调色板命名和行注释的可读代码。
