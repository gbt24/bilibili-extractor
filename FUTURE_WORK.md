## Windows Cookie Issue (TODO)

SESSDATA 是 HttpOnly cookie，JS 读不到，需要手动从 F12 DevTools 复制。
Netscape 格式要求 Tab 分隔（不能空格），且 yt-dlp 会覆写 --cookies 文件。

**解决方案（待实现）：**
1. get_cookies.py 改用 Python subprocess 调 yt-dlp 导出 cookie 到独立文件
2. 或编写 Edge 扩展自动导出 HttpOnly cookie
3. 或提供格式校验脚本，自动检测 Tab/空格问题

**当前 workaround：** Mac/Linux 上直接用 --cookies-from-browser
