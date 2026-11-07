# VERICUT 9.6 配置文件与环境变量位置

| 配置文件 / 目录 | 用途 | 位置 | 证据 |
| :-- | :-- | :-- | :-- |
| `vericut.bat` | 主启动器 + 全部 CGTECH_* 环境变量定义 + 参数透传 | `E:\windows64\commands\vericut.bat` | E-V01 逐行读取 |
| `vericut_agent.bat` | Agent 定制启动器（复制原 bat + 注入 CGTECH_VCPROJECT / CGTECH_TRANSACTION_LOG） | `E:\windows64\commands\vericut_agent.bat` | E-V06 |
| `cgtenv.bat` | 许可证服务器主机 LSHOST 与基础环境（许可证细节 out-of-scope，不展开） | `E:\windows64\commands\cgtenv.bat` | E-V01 |
| 事务审计日志 | GUI 操作审计（ActionInit/TP_GET_NC_*/ActionMainPlay） | `%USERPROFILE%\cgtech_96_transaction.log`（bat 第 108 行 `TRANS_LOG=%HOMEDRIVE%%HOMEPATH%\...`）；异常轮次自动改名 `cgtech_96_transaction_N.log` | E-V01/E-V06 |
| 用户偏好 prefs | 会话偏好；`CGTECH_USERNAME=<string>` 时文件名变为 `cgtech_96_<string>.prefs` | 用户目录（bat 注释区） | E-V01 注释 documented-not-probed |
| 样本/库目录 | 刀具库样本、TLS、支持文件 | `E:\samples\`、`E:\library\`、`E:\samples\TLS`、`E:\samples\Support_files`（CGTECH_SAMPLES/CGTECH_LIBRARY 指向） | E-V01 |
| 帮助系统 | 本地帮助 `E:\hhelp`；在线 `https://help96.vericut.com/hhelp` | CGTECH_HELP_LOCAL_DIR / CGTECH_HELP_ONLINE_URL | E-V01 |
| 语言包 | 简体中文资源 `E:\classes\lang\chinese_simplified` | CGTECH_LANGUAGE | E-V01 |
| Force 材料库 | Force 模块材料定义 | `E:\force_materials`（CGTECH_FORCE_MATERIALS） | E-V01 |
| 色彩表 | Auto-Diff/显示色彩 | `E:\windows64\vericut\rgbhues.txt`（CGTECH_RGB_TXT） | E-V01 |
| VTPD 资源库 | 机床/组件资源数据库 | `E:\windows64\resources\VTPD.db`（CGTECH_VTPD_FILE） | E-V01 |
| 表面纹理 | 模型显示纹理 | `E:\library\surface_textures` | E-V01 |
| KRL 库 | KUKA Robot Language 系统文件 | `E:\library\krl`（CGTECH_KRL_LIBRARY） | E-V01 |
| JRE | 内置 Java 运行时 | `E:\windows64\jre\bin\javaw.exe` | E-V01 |
| JavaFX | JavaFX 模块库 | `E:\windows64\javafx\lib` | E-V01 |
| 类路径 | CGTech 主类 | `E:\classes;E:\classes\CGTech.jar` | E-V01 |
| 更新检查 | 在线更新检查地址 | `https://www.cgtech.com/software_update_check.txt`（CGTECH_CHECK_UPDATE） | E-V01 |

## 环境变量速查（可被 Agent 注入）

```text
CGTECH_INSTALL=E:\
CGTECH_PRODUCTS=E:\windows64
CGTECH_CLASSES=E:\classes
CGTECH_LIBDIR=E:\library\
CGTECH_LIBRARY=E:\library\;E:\samples\TLS;E:\samples\Support_files
CGTECH_LOCALE=chinese_simplified
CGTECH_LANGUAGE=E:\classes\lang\chinese_simplified
CGTECH_DEFAULT_UNITS=MILLIMETER
CGTECH_VA_SHOW=TRUE
CGTECH_VCPROJECT=<绝对路径.vcproject>     # Agent 注入：自动加载工程
CGTECH_TRANSACTION_LOG=Yes                 # Agent 注入：写事务审计日志
```

> 注：许可证服务器、授权/激活相关文件（`CGTECH_LICENSE`、CGTECH_SLM_* 等）属 out-of-scope，本知识库不展开其内容。
