# siemens__siemens_paramprg__absgoto.md

> 官方帮助主题源文件: `source/chm_cn/siemens/siemens_paramprg/absgoto.htm`

---

绝对跳转
1.功能
NC程序在运行时以写入时的顺序执行程序段。
程序在运行时可以通过插入程序跳转指令改变执行顺序。
跳转目标只能是有标记符的程序段。此程序段必须位于该程序之内。
绝对跳转指令必须占用一个独立的程序段。
2.编程
GOTOF Lable ；先前跳转
GOTOB Lable ；向后跳转
AWL 说明
GOTOF 向前跳转（向程序结束的方向跳转）
GOTOB 向后跳转（向程序开始的方向跳转）
Lable 所选的标记符
