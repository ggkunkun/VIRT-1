# siemens__siemens_paramprg__example.md

> 官方帮助主题源文件: `source/chm_cn/siemens/siemens_paramprg/example.htm`

> 关联官方截图(1):
> - `source/chm_cn/chm_cn/siemens/siemens_paramprg/images/example%20_clip_image002.jpg`

---

程序跳转举例
任务 圆弧上点的移动：
已知：起始角： 30° R1
圆弧半径： 32mm R2
位置间隔： 10° R3
点数： 11 R4
圆心位置，Z轴方向 50mm R5
圆心位置，X轴方向 20mm R6
编程举例： N10 R1=30 R2=32 R3=10 R4=11 R5=50 R6=20
；赋初始值
N20 MA1:G0 Z=R2*COS(R1)+R5 X=R2*SIN(R1)+R6
；坐标轴地址的计算及赋值
N30 R1=R1+R3 R4=R4-1
N40 IF R4＞0 GOTOB MA1
N50 M2
说明 在程序段N10中给相应的计算参数赋值。在N20中进行坐标轴X和Z的数值计算
并进行赋值。
在程序段N30中R1增加R3角度；R4减小数值1。
如果R4＞0,则重新执行N50，用M2结束程序。
