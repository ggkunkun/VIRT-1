# fanuc__fanuc0i_t__fanuc0i_t_std.md

> 官方帮助主题源文件: `source/chm_cn/fanuc/fanuc0i_t/fanuc0i_t_std.htm`

> 关联官方截图(32):
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/images/fanuc0i_t_std_clip_image001.jpg`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan01.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan02.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan03.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan14.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan12.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan13.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan04.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan15.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan11.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/an02.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan17.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan16.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/an03.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan18.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan20.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan19.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/fanuc0i_t_std_clip_image001.jpg`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/an05.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/an06.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/an07.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/an08.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan05.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan06.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan07.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan21.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan08.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan22.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan23.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan26.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_m/pic/xan24.gif`
> - `source/chm_cn/chm_cn/fanuc/fanuc0i_t/Pic/xan25.gif`

---

北京FANUC 0iM标准操作面板
返回<<<
机床操作面板位于窗口的右下侧，如下图所示。主要用于控制机床的运动和选择机床运行状态
，由模式选择旋钮、数控程序运行控制开关等多个部分组成，每一部分的详细说明如下。
AUTO：进入自动加工模式。
EDIT: 用于直接通过操作面板输入数控程序和编辑程序。
MDI：手动数据输入。
iNC: 增量进给。
手轮方式移动台面或刀具
JOG：手动方式，手动连续移动台面或者刀具。
DNC位置在用232电缆线连接PC机
和数控机床
，选择数控程序文件传输。
REF：回参考点
。
数控程序运行控制开关
程序运行开始；模式选择旋钮在“AUTO”和“MDI”位置时按下有效，其余时间按下无效。
程序运行停止，在数控程序运行中，按下此按钮停止程序运行。
机床主轴手动控制开关
手动开机床主轴正转
手动开机床主轴反转
手动关机床主轴
手动移动机床台面按钮
单步进给量控制旋钮
选择手动台面时每一步的距离。X1为0.001毫米，X10.
为0.01毫米，X100为0.1毫米，X1kK为1毫米。置光标于旋钮上，点击鼠标左键选择。
进给速度(F)调节旋钮
调节数控程序运行中的进给速度，调节范围从0～120% 。置光标于旋钮上，点击鼠标左键转动。
主轴速度调节旋钮
调节主轴速度，速度调节范围从50～120%。
手脉
把光标置于手轮上，按鼠标左键，移动鼠标，手轮顺时针转，机床往正方向移动，手轮逆时针转，机床往负方向移动。
单步执行开关
每按次执行一条数控指令。
程序段跳读
自动方式按下次键,跳过程序段开头带有“/”程序。
程序停
自动方式下，遇有M00程序停止。
机床空转
按下此键,
各轴以固定的速度运动。
手动示教
冷却液开关
按下此键, 冷却液开。
在刀库中选刀
按下此键, 刀库中选刀。
程序编辑开关
置于“ON”位置,可编程序。
程序重启动
由于刀具破损等原因自动停止后,程序可以从指定的程序段重新启动。
程序锁开关
按下此键, 机床各轴被锁住。
