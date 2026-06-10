#!/usr/bin/env python3
"""
Generate a JavaScript bookmarklet for extracting Bilibili cookies.

Usage:
    python get_cookies.py
    # Copy the printed bookmarklet code
    # Create a new bookmark in Edge, paste the code as URL
    # Open bilibili.com, click the bookmark → cookies.txt generated
"""

BOOKMARKLET = """javascript:(function(){
  var c=document.cookie.split(';').reduce(function(a,v){
    var p=v.trim().split('=');
    a[p[0].trim()]=p.slice(1).join('=');
    return a;
  },{});
  var k=['SESSDATA','bili_jct','DedeUserID','sid'];
  var t='# Netscape HTTP Cookie File\\n';
  k.forEach(function(n){
    if(c[n]) t+='.bilibili.com\\tTRUE\\t/\\tFALSE\\t9999999999\\t'+n+'\\t'+c[n]+'\\n';
  });
  var blob=new Blob([t],{type:'text/plain'});
  var a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download='cookies.txt';
  a.click();
  alert('cookies.txt 已下载！放入项目目录后运行：\\npython pipeline.py --cookies-file cookies.txt');
})();"""

JS_CONSOLE = """// 在 B 站页面按 F12 → Console → 粘贴以下代码 → 回车
var c=document.cookie.split(';').reduce(function(a,v){
  var p=v.trim().split('=');
  a[p[0].trim()]=p.slice(1).join('=');
  return a;
},{});
var k=['SESSDATA','bili_jct','DedeUserID','sid'];
var t='# Netscape HTTP Cookie File\\n';
k.forEach(function(n){
  if(c[n]) t+='.bilibili.com\\tTRUE\\t/\\tFALSE\\t9999999999\\t'+n+'\\t'+c[n]+'\\n';
});
console.log(t);
copy(t);
console.log('已复制到剪贴板！粘贴到 cookies.txt');"""


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║               Bilibili Cookie 提取工具                        ║
╚══════════════════════════════════════════════════════════════╝

方式一（推荐）：书签法
  1. 在 Edge 中新建一个书签（Ctrl+D）
  2. 书签名任意，URL 粘贴下面整段代码：
""")
    print(BOOKMARKLET)
    print("""
  3. 打开 bilibili.com，确认已登录
  4. 点击刚创建的书签 → 自动下载 cookies.txt
  5. 把 cookies.txt 放到 bilibili-extractor 目录
  6. python pipeline.py --cookies-file cookies.txt

────────────────────────────────────────────────────────

方式二：F12 控制台
  1. 打开 bilibili.com，确认已登录
  2. 按 F12 → Console 标签
  3. 粘贴以下代码，回车：
""")
    print(JS_CONSOLE)
    print("""
  4. 自动复制到剪贴板，粘贴到项目目录的 cookies.txt

────────────────────────────────────────────────────────

注意：SESSDATA 是你 B 站登录凭证，不要分享给任何人。
""")


if __name__ == "__main__":
    main()
