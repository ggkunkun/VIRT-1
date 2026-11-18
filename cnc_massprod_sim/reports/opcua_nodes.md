# OPC UA 信息模型（量产对接）

| 节点 | 含义 |
|---|---|
| Production.State | 运行状态 IDLE/RUNNING/ALARM/COMPLETE |
| Production.Part | 当前工件号 |
| Production.ProgramHash | 当前 NC 程序 SHA256（一致性追溯） |
| Production.BatchCount | 批量计数 |
| Production.CycleTime_s | 实时节拍 |
| Production.MinClearance_mm | 最小夹具间隙（撞机预警） |
| Production.Cpk | 关键特征过程能力（超差预警） |
| Production.ToolWear_pct | 刀具磨损百分比 |
| Production.AlarmCode | 报警码 |
| Production.AlarmText | 报警文本 |
| basis | OPC UA 信息模型（asyncua 实测栈） |
