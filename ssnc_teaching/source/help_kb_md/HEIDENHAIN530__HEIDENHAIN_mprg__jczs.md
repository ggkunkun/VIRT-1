# HEIDENHAIN530__HEIDENHAIN_mprg__jczs.md

> 官方帮助主题源文件: `source/chm_cn/HEIDENHAIN530/HEIDENHAIN_mprg/jczs.htm`

> 关联官方截图(8):
> - `source/chm_cn/chm_cn/HEIDENHAIN530/HEIDENHAIN_mprg/images/assistant_clip_image004.jpg`
> - `source/chm_cn/chm_cn/HEIDENHAIN530/HEIDENHAIN_mprg/images/assistant_clip_image008.jpg`
> - `source/chm_cn/chm_cn/HEIDENHAIN530/HEIDENHAIN_mprg/images/assistant_clip_image010.jpg`
> - `source/chm_cn/chm_cn/HEIDENHAIN530/HEIDENHAIN_mprg/images/assistant_clip_image014.jpg`
> - `source/chm_cn/chm_cn/HEIDENHAIN530/HEIDENHAIN_mprg/images/assistant_clip_image018.jpg`
> - `source/chm_cn/chm_cn/HEIDENHAIN530/HEIDENHAIN_mprg/images/assistant_clip_image022.jpg`
> - `source/chm_cn/chm_cn/HEIDENHAIN530/HEIDENHAIN_mprg/images/assistant_clip_image028.jpg`
> - `source/chm_cn/chm_cn/HEIDENHAIN530/HEIDENHAIN_mprg/images/assistant_clip_image032.jpg`

---

基础知识
位置编码器和参考点
机床轴上的位置编码器用于记录机床工作台或刀具位置。线性轴一般用直线光栅尺，旋转工作台和倾斜轴一般用角度编码器。
当机床轴运动时，相应位置编码器生成电信号。TNC处理该信号并精确地计算出机床轴的实际位置。
如果电源断电，计算的位置将不再对应于机床实际位置。要恢复二者之间的对应关系，需要使用带参考点的增量式位置编码器。位置编码器上刻有一个或多个参考点，当移到一个参考点时，
编码器向TNC发送一个信号。TNC用这个信号可以重新建立显示位置与机床位置的对应关系。如果直线光栅尺带距离编码参考点的话，执行参考点回零时，机床轴移动量不超过20毫米，角度
编码器不超过20度。
如果使用绝对位置编码器的话，开机后绝对位置值立即就传给数控系统。因此开机后就能立即重新建立机床运动位置与实际位置的对应关系。
参考系统
参考系统用于确定平面或空间中的位置。所有位置数据都是相对一个预定点并用坐标来描述的。
笛卡尔坐标系统（直角坐标系统）是由X.Y和Z三个坐标轴建立的。三轴相互垂直并相交于一点，该点被称为原点。坐标值代表着在这些坐标轴方向上距原点的距离。因此平面上的位置用两坐标描述，
空间中的位置用三坐标描述。
相对原点的坐标称为绝对坐标。相对坐标是相对坐标系内定义的其他任何已知位置（参考点）的坐标。相对坐标值还被称为增量坐标值。
使用铣床时，刀具运动是相对笛卡尔坐标系，右图所示为描述机床轴方向的笛卡儿坐标系。右图显示了用+右手规则+记忆三个轴的方向，中指指向
从工作朝向刀具的刀具轴（Z轴）正方向，拇指指向X轴正方向：食指指向Y轴正方向。
iTNC 530最多可控制9个轴。U、V和W为复制线性轴， 它们分别平行于X、Y、Z轴。旋转轴为A、B和C。右下图所示为主坐标轴与辅助线性轴和旋转轴的对应关系。
工件的绝对与增量位置
工件绝对位置
绝对坐标是相对（原）坐标系统原点的位置坐标值。工件上的每个位置都唯一地由其绝对坐标确定。
例1：用绝对坐标标注孔的位置
孔1：X=10mm Y=10mm
孔2：X=30mm Y=20mm
孔3：X=50mm Y=30mm
工件增量位置
增量坐标是指相对刀具的上一个编程名义位置，这个位置被用作相对（虚拟）原点。如用增量坐标来编写零件程序，刀具将按前一位置与后一位置间的距离来运动。这也称作链尺寸。
如要用增量坐标编程一个位置，需在轴前输入前缀"I"
例2：用增量坐标孔注孔的位置
孔4的绝对坐标
X=10mm
Y=10mm
孔5，相对4
X=20mm
Y=10mm
孔6，相对5
X=20mm
Y=10mm
设置原点
工件图以工件的某元素，通常以角点，作为绝对原点，设置原点时，应先将工件与机床轴对正，然后将刀具沿各轴移至相当于工件的一个已知位置处。
然后将TNC的坐标显示置零或某预定的位置值。这样就为工件建好了参考系统，并将它用于TNC显示及零件程序中。
如果工件图的尺寸标注不符合NC要求，可将工件上的某位置或一个角点设置为原点，这个点的选择应便于标注工件上的其它位置尺寸。
举例
工件图纸上的空（1-4）尺寸为相对X=0 Y=0坐标的绝对原点。孔（5-7）的尺寸为相对绝对坐标X=450，Y=750的相对原点。用DATUM SHIFT（原点平移）
循环可以临时将原点设置在位置X=450，Y=750处，使编程孔（5-7）时不涉及其他计算。
