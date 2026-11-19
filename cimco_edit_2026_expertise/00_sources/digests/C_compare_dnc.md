# 官方语料摘录 C_compare_dnc（共 22 页，源自 docs.cimco.com/en/docs/edit/2026/）


======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/
TITLE: DNC Setup
======================================================================
PDF
DNC Setup
DNC Setup
This section describes the configuration options in the
DNC Setup
dialog.
The dialog can be opened from the
Transmission
menu or the
Setup
menu under the Transmission tab.
Subsections
Standard Serial Protocol
FTP Client Protocol
DNC Setup dialog.
Machines
This section shows a list of machines (machine configurations). The options below in the
Configuration
section are specific to the machine selected in this list.
Protocol
Use this dropdown to select the communication protocol for the selected machine.
For transfers via serial select the
Standard Serial Protocol
.
For transfers via FTP select the
FTP Client Protocol
.
Port information
Shorthand of important connection settings.
For a serial connection the line 'COM1, 9600, 7E2' has the following meaning:
Port: COM1
Baud rate: 9600
Data bits: 7
Parity: E (even)
Stop bits: 2
For an FTP connection the line 'cimco@192.168.254.231' has the following meaning:
Username: cimco
CNC IP Address: 192.168.254.231
Machine Type
Select the machine type from this list. The machine type is used to determine the default load/save directories, how to detect tool changes etc. during a transfer.
Machine types are configured in the
File Types
section in the Editor Setup.
Setup
Click this button to enter the configuration dialog for the selected machine.
Rename
Click this button to rename a machine configuration.
Add New
Click this button to add a new configuration. The following dialog appears:
Add a new machine.
Enter a name and select a machine template to preconfigure the new machine. You can select an existing machine configuration or one of the default templates:
FTP Client
Generic Serial Connected CNC
Okuma Template
Click
OK
to add the new machine or
Cancel
to cancel the operation.
Delete
Click this button to delete a configuration. You will be prompted to confirm the deletion.
OK
Click this button to apply the configuration and close the dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/ftp-client-protocol/
TITLE: FTP Client Protocol
======================================================================
PDF
DNC Setup
FTP Client Protocol
FTP Client Protocol
This section describes the configuration options in the
FTP Client Protocol
.
Subsections
Port
Send/Receive
Version Info
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/ftp-client-protocol/port/
TITLE: Port
======================================================================
PDF
DNC Setup
FTP Client Protocol
Port
Port
This section allows you to configure the FTP port settings.
Port settings.
FTP Client
Server address
Use this field to specify the IP address of the FTP server. Example 127.0.0.1.
Username
Use this field to specify the username used for the client connection.
Password
Use this field to specify the username used for the client connection.
Directories
PC default path
Use this field to specify the default path for the PC side files. Leaving this empty will result in default path C:\ being used.
FTP server default path
Use this field to specify the default path on the FTP server side. Path should be FTP compliant format: /[DIR] or /[DIR]/. Path is written in absolute path from FTP server root.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/ftp-client-protocol/send-receive/
TITLE: Send/Receive
======================================================================
PDF
DNC Setup
FTP Client Protocol
Send/Receive
Send/Receive
This section allows you to configure the FTP send and receive settings.
Transmission setup.
Send/Receive window
Use split window
Check this to use a split window when sending and receiving files. The split window is only used if no files is specified when starting send operation. The split window is always used when receiving file from FTP server.
Receive to default PC directory
Check this to always receive files from the FTP server to the default local directory.
Allowed split window actions
Send
Check this to allow the FTP Client to send files to the FTP Server.
Receive
Check this to allow the FTP Client to receive files from the FTP Server.
Local deletion
Check this to allow the split window to delete files and folders on local side.
Local renaming
Check this to allow the split window to rename files and folders on the local side.
Local directory change
Check this to allow the split window to change directory on the local side.
Local directory creation
Check this to allow the split window to create directories on the local side.
Remote deletion
Check this to allow the split window to delete files and folders on the FTP server.
Remote Renaming
Check this to allow the split window to rename files and folders on the FTP server.
Remote directory change
Check this to allow the split window to change directory on the FTP server. If this is disabled, only the default FTP server directory is listed. No folders will be shown in file list.
Remote directory creation
Check this to allow the split window to create directories on the FTP server.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/ftp-client-protocol/version-info/
TITLE: Version Info
======================================================================
PDF
DNC Setup
FTP Client Protocol
Version Info
Version Info
This section allows you to see the version of the FTP Client Protocol.
Version info.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/standard-serial-protocol/
TITLE: Standard Serial Protocol
======================================================================
PDF
DNC Setup
Standard Serial Protocol
Standard Serial Protocol
This section describes the configuration options in the
Standard Serial Protocol
.
Subsections
Port
Transmit
Receive
Directories
Version Info
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/standard-serial-protocol/directories/
TITLE: Directories
======================================================================
PDF
DNC Setup
Standard Serial Protocol
Directories
Directories
This section allows you to configure the Directories settings.
Transmit and Receive directories setup.
Default Send
Default send directory
Specify the default send path in this field, or click on the folder icon
to the right to select a directory.
Default extension
Use this field to specify the default extension of files to be sent.
Additional extensions
Use this field to specify additional extensions for files to be sent.
Default Receive
Default receive directory
Specify the default receive directory, or click on the folder icon
to the right to select a directory.
Default extension
Use this field to specify the default extension for received files.
Additional extensions
Use this field to specify additional extensions for received files.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/standard-serial-protocol/port/
TITLE: Port
======================================================================
PDF
DNC Setup
Standard Serial Protocol
Port
Port
This section allows you to configure the Serial port settings.
Serial port settings.
Serial Port Settings
Port
List of the serial ports on the local PC. Select the one you wish to use with this machine configuration.
Baud rate
The transmission speed in bits per second. Select the desired Baud rate from the drop-down list.
Stop bits
Select the number of stop bits appended after each character in the communication to separate the data bits.
The number of stop bits required depends on the CNC control. Please refer to the reference manual for more details.
Data bits
Select the number of bits in each character. By default, the 7-bit ASCII code is used for NC data transmission.
Parity
The parity is an error checking method which indicates if a transmission was successful or not, by adding a 'parity bit' (8th bit when using 7-bit ASCII code for data transmission) to ensure the number of bits with the value '1' in a set of bits is
even
or
odd
.
The method can operate in different modes:
None
: Is selected when no parity error checking is going to be used.
Even
parity: An even number of 1's is used in each character.
Odd
parity: An odd number of 1's is used in each character.
Only for special cases (test purposes):
Mark
parity: The parity bit is always '1' and the line is 'low'.
Space
parity: The parity bit is always '0' and the line is 'high'.
Flow Control Settings
Flow control
The handshake procedure for synchronizing the communication between the computer and the CNC control. There are two types of flow control:
Software handshake
uses the XOn/XOff ASCII characters.
Hardware handshake
uses the RTS/CTS control lines in the RS-232 communication specifications.
You can select one of the following flow control methods from the dropdown list:
None
: No flow control is performed.
Software
: Software handshake is used for the flow control.
Hardware
: Hardware handshake is used for the flow control.
Hardware and Software
: Both Hardware and Software handshakes are used.
Enable DTR
Check this box to set DTR high.
Enable RTS
Check this box to set RTS high.
Advanced Port Settings
Check parity
If you want CIMCO Edit 2026 to report parity errors, then mark the
Check parity
box. Every time an error occurs, the specified character is inserted into the file at the receiving point.
Non standard XOn and XOff characters can be specified.
Insert on parity error
Use this field to specify a character to insert in the received file, if a parity error occurs while receiving data from the remote machine. If the field is left blank, no character is inserted.
XOn character
Use this field to specify the XOn character. If the field is left blank, the standard XOn character is used. If your machine needs a non-standard XOn character, you can specify it here.
XOff character
Use this field to specify the XOff character. If the field is left blank, the standard XOff character is used. If your machine needs a non-standard XOff character, you can specify it here.
You can specify the
XOn
,
XOff
, and
Insert on parity error
characters by entering the ASCII character, i.e. enter
$
to get ASCII character 36, or you can enter the ASCII value like this
\36
.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/standard-serial-protocol/receive/
TITLE: Receive
======================================================================
PDF
DNC Setup
Standard Serial Protocol
Receive
Receive
This section allows you to configure the Receive settings.
Receive settings.
Receive Settings
CR/LF
Use this field to specify the line feed character(s).
If you select
Auto
, the DNC will try to auto-detect the CR/LF combination used. If the remote machine does not use any of the standard combinations of ASCII 13 and ASCII 10, you must enter the appropriate CR/LF combination manually.
The normal combination is ASCII 13 followed by ASCII 10. ASCII 13 and ASCII 10 have no character representation, so they must be entered as \13 and \10 respectively.
Omit lines containing
Excludes lines containing one or more selected characters. The consequence of entering anything here is that any line containing one of these characters or strings will be discarded when received.
Omit lines with string
Use this field to remove lines containing the specified string. You can specify the characters by entering the ASCII characters, i.e. enter '$' (without the ' ') to get ASCII character 36, or you can enter the ASCII value like this '\36' (again without the ' ').
Remove characters
Selected characters will automatically be removed from the received stream. You can select None, ASCII 0 or All below ASCII 32 from the drop-down list if one of those is appropriate.
Omit empty lines
Check this field if empty lines should not be saved.
Start trigger
Start triggers are characters indicating that CIMCO Edit 2026 should start saving incoming data. If no start trigger is used and the field therefore is left empty, CIMCO Edit will start saving at the beginning of the file.
The start trigger is the first sequence of characters received.
End trigger
End triggers are characters indicating that CIMCO Edit 2026 should stop saving incoming data. If no end trigger is used and the field therefore is left empty, CIMCO Edit 2026 will continue to save until the end of the file, where a timeout occurs.
The end trigger is the last sequence of characters received.
Receive timeout (seconds)
Indicates the time delay after the last character has been received from the remote machine, until the computer concludes that the receiving operation is finished. If no end trigger is specified, you should specify a value here, or you will have to stop the receive process manually from the receive status dialog.
Advanced Receive Settings
Send XOn
When this field is checked, the DNC will send an XOn character when it is ready to receive data.
Send at start of reception
Specify a string that should be sent to the CNC when a receive operation is started.
When entering characters in one of the character entry fields, the characters can be entered in two ways: You can enter the characters themselves, like
$*
to get ASCII character 36 followed by ASCII 42, or you can enter the ASCII values of the characters like
\36\42
.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/standard-serial-protocol/transmit/
TITLE: Transmit
======================================================================
PDF
DNC Setup
Standard Serial Protocol
Transmit
Transmit
This section allows you to configure the Transmit settings.
Transmission setup.
Transmit Settings
CR/LF
In this field, you can select the carriage-return or line-feed character(s) from the drop-down list, or you can enter them manually.
ASCII 13 and ASCII 10 have no character representation, so they must be entered as
\13
and
\10
respectively.
Start trigger
Use this field to specify the start trigger. The DNC will start transmitting data from the first line in the file that contains the specified start trigger. If no start trigger is specified, the transmission will start at the beginning of the file.
End trigger
Use this field to specify the end trigger.
The line containing the end trigger is not transmitted.
Send at start of feed
Here, you can specify a character or a string that should be sent at the start of the transmission.
Send at end of feed
Specify a character or a string that should be sent at the end of the transmission.
Omit lines containing
Excludes lines containing one or more selected characters. The consequence of entering anything here is that any line containing one of these characters or strings will not be transmitted.
Remove characters
Use this field to specify characters that should be removed from the transmitted data.
Break after receiving characters
Ends the transmission to the control after the specified number of characters have been sent, even if the program is not finished. If this field is left empty, any incoming characters are ignored.
Handshake timeout (seconds)
The chosen time that CIMCO Edit 2026 should wait after receiving a stop flow signal (XOff and/or CTS Low) from a remote machine before it terminates the connection. If the timeout value is not specified, it will wait until a start flow is received.
Delay before each line (ms)
Specify the time in milliseconds CIMCO Edit 2026 should wait before it begins transmitting a new line.
Wait for XOn
This box is checked if you wish CIMCO Edit 2026 to wait for an Xon before transmitting data. This option is only available if Software handshake is enabled in the port settings.
Wait for 'Start' button
Check this field if the transmission should not start until you click the Start button on the transmit status dialog.
Remove ASCII 0's
Check this field if ASCII 0's should be removed from the transmitted data.
Remove white spaces
White spaces (ASCII 32) and tabs (ASCII 9) are removed automatically from the file transmitted to the remote machine.
Replace tabs with spaces
Converts tabs (ASCII 9) to spaces (ASCII 32) before sending the file to the remote machine.
Send files with non-standard CR/LF
Check this field if you wish to send files that contain non-standard linefeed characters like \CR\LF\LF or \CR\CR.
When entering characters in one of the character entry fields, the characters can be entered in two ways: You can enter the characters themselves, like
$*
to get ASCII character 36 followed by ASCII 42, or you can enter the ASCII values of the characters like
\36\42
.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/dnc-setup/standard-serial-protocol/version-info/
TITLE: Version Info
======================================================================
PDF
DNC Setup
Standard Serial Protocol
Version Info
Version Info
This section allows you to see the version of the Standard Serial Protocol.
Version info.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/file-compare/
TITLE: File Compare
======================================================================
PDF
Program Tabs
File Compare
File Compare
This section describes the options in the
File Compare
tab.
Subsections
File Compare
Go To
Sync
Other
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/file-compare/file/
TITLE: File Compare
======================================================================
PDF
Program Tabs
File Compare
File Compare
File Compare
This section describes the options in the
File Compare
menu which are used for comparing files.
File Compare menu.
Menu options
Compare with Window
Compares the file in the current window with a file in another. When more than two files are open, CIMCO Edit will ask you to select the file you want to compare with.
Compare with File
Compares the file in the current window with a file. The other file is opened through the
Open file
dialog.
Compare File with File
Compares two files which are not already in a window. The files are opened using the
Open file
dialog.
End File Compare
The file compare session is stopped and both files are left open.
Close Left Window
Select this to close the file compare window on the left side.
Close Right Window
Select this to close the file compare window on the right side.
Setup
Select this to enter the
File Compare
section in the Editor Setup.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/file-compare/goto/
TITLE: Go To
======================================================================
PDF
Program Tabs
File Compare
Go To
Go To
This section describes the options in the
Go To
menu which are used to step through the differences found during a file compare.
Go To menu.
Menu options
Next Difference /
Ctrl+Down Arrow
Select this to go to the next difference.
Previous Difference /
Ctrl+Up Arrow
Select this to go to the previous difference.
Go to First Difference
Select this to go to the first difference.
Go to Last Difference
Select this to go to the last difference.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/file-compare/other/
TITLE: Other
======================================================================
PDF
Program Tabs
File Compare
Other
Other
This section describes the options in the
Other
menu.
Other menu.
Menu options
Save Compare File
Select this option to save lines with differences to a .txt file.
Single Step Through Differences
Enable this option to only synchronize the line where the cursor is positioned.
By default, CIMCO Edit synchronizes blocks of lines, such as where two or three consecutive lines contain differences. By enabling this option, you can focus on one line at a time.
File Compare Setup
Select this to enter the
File Compare
section in the Editor Setup.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/file-compare/sync/
TITLE: Sync
======================================================================
PDF
Program Tabs
File Compare
Sync
Sync
This section describes the options in the
Sync
menu which are used to synchronize differences.
When you synchronize a difference, the selected difference is copied from one window to another. The options described below determine the synchronization direction (from right to left or from left to right).
When the text is moved from one to another window, the line is no longer highlighted. This is because the texts in both windows are identical after synchronization.
Sync menu.
Menu options
Sync Left /
Ctrl+Left Arrow
Synchronizes current difference from right to left window.
Sync Right /
Ctrl+Right Arrow
Synchronizes current difference from left to right window.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/
TITLE: Transmission
======================================================================
PDF
Program Tabs
Transmission
Transmission
This section describes the options in the
Transmission
tab.
CIMCO Edit enables the transfer (sending and receiving) of NC programs to and from CNC machines through serial or FTP connection.
For transfers via serial refer to
Standard Serial Protocol
.
For transfers via FTP refer to
FTP Client Protocol
.
Both serial and FTP are configured in the
DNC Setup
dialog which can be opened from the
Transmission
menu or the
Setup
menu under the Transmission tab. The DNC Setup dialog is separate from the Editor Setup and cannot be accessed from this.
CIMCO Edit 2026 must be licensed for DNC operations to use this option.
Subsections
Transmission
Machine
Setup
Transmit/Receive Dialogs
FTP Transfer Dialog
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/machine/
TITLE: Machine
======================================================================
PDF
Program Tabs
Transmission
Machine
Machine
This section describes the options in the
Machine
menu which are used select the machine you want to send to or receive from.
Machines are configured in the
DNC Setup
dialog.
Machine menu.
Menu options
Machine Type
Use this dropdown to select the machine you want to send to or receive from.
Status
Select this option to show the
Transmit dialog
(if this has been hidden).
This option is disabled for machines using FTP.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/setup/
TITLE: Setup
======================================================================
PDF
Program Tabs
Transmission
Setup
Setup
This section describes the option in the
Setup
menu which is used to open the
DNC Setup
dialog.
Setup menu.
Menu options
DNC Setup
Select this option to open the
DNC Setup
dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/split-window/
TITLE: FTP Transfer Dialog (Split Window)
======================================================================
PDF
Program Tabs
Transmission
FTP Transfer Dialog
FTP Transfer Dialog (Split Window)
The
FTP Transfer
dialog, also known as the
Split Window
, operates similarly to many FTP clients, displaying the local PC on the left and the remote FTP server (CNC) on the right.
FTP Transfer dialog.
PC path (dropdown on left side)
Use this dropdown to select a path on the local PC or network. Use the folder icon on the right side of the dropdown to go to the parent directory.
When connected, the FTP Transfer dialog shows the contents of the default local directory.
The default local directory can be configured in the
Port
section in the DNC Setup.
CNC path (right side)
When connected, the FTP Transfer dialog shows the contents of the default remote directory. Use the folder icon on the right side of the path field to go to the parent directory.
The default remote directory can be configured in the
Port
section in the DNC Setup.
Refresh
Click this button to refresh both the local and remote directories.
Send to remote
Click this to send the selected file(s) from the local side (PC) to the remote side (server).
Receive from remote
Click this to send the selected file(s) from the remote side (server) to the local side (PC).
New folder
Click this button to create a new folder on either the local side or remote side.
The options
Local directory creation
and
Remote directory creation
must be enabled in the
Send/Receive
section in the DNC Setup.
Rename
Click this button to rename the selected file or folder on either the local side or remote side.
The options
Local renaming
and
Remote renaming
must be enabled in the
Send/Receive
section in the DNC Setup.
Delete
Click this button to delete the selected file or folder on either the local side or remote side.
The options
Local deletion
and
Remote deletion
must be enabled in the
Send/Receive
section in the DNC Setup.
File Type
Use this field to specify the file type used for sending programs.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/transmission/
TITLE: Transmission
======================================================================
PDF
Program Tabs
Transmission
Transmission
Transmission
This section describes the options in the
Transmission
menu which are used to send and receive programs to and from CNC machines.
Transmission menu.
Menu options
Send
Select this option to send the current NC program to the machine selected in the dropdown in the
Machine
menu.
The
Transmit status
dialog will appear showing the transfer status.
Click the down arrow to see additional options.
This option is not available for FTP.
Send Selected Lines
Select this option to send a selected block of lines to the machine selected in the dropdown in the
Machine
menu.
The
Transmit status
dialog will appear showing the transfer status.
This option is not available for FTP.
Send File
Use this option to locate a file and send it to the machine selected in the dropdown in the
Machine
menu.
For serial, the
Transmit status
dialog will appear showing the transfer status.
For FTP, the
FTP Transfer
dialog will appear, however, only if the option
Use split window
is enabled under
Send/Receive Settings
in the DNC Setup for the FTP Client Protocol.
Click the down arrow to see a list of recently sent files.
Receive File
Select this option to receive an NC program from the machine selected in the dropdown in the
Machine
menu. The file will be saved without opening it.
Select this option to open the
Receive File
dialog
Locate the folder where the file should be saved to
Enter a filename and select a file type
Click the
Save
button
The
Receive status
dialog will appear showing the transfer status
When using FTP, the
FTP Transfer
dialog will show when receiving a file from an FTP server.
Click the down arrow to see a list of recently received files.
Receive
Select this option to receive an NC program from the machine selected in the dropdown in the
Machine
menu. The program will be opened in a new window.
The
Receive status
dialog will appear showing the transfer status.
This option is not available for FTP.
Receive Into Current Window
Select this option to receive an NC program from the machine selected in the dropdown in the
Machine
menu. The program will be inserted into the current window.
The
Receive status
dialog will appear showing the transfer status.
This option is not available for FTP.
DNC Setup
Click this to open the
DNC Setup
dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/transmission/untitled-104/
TITLE: Transmit/Receive Dialogs
======================================================================
PDF
Program Tabs
Transmission
Transmit/Receive Dialogs
Transmit/Receive Dialogs
The Transmit Status and Receive Status dialogs are essentially the same dialog with minor variations to accommodate either sending or receiving operations.
Transmit Status Dialog
Transmit Status dialog.
Signals (top left)
This section shows the key signals of the serial data transmission according to EIA RS-232-C standard for serial communication. The signals light up when activated.
Information (top right)
This section shows information about the current transmission such as Machine name, Filename, Bytes sent, etc.
Progress Bar
The progress bar indicates the current progress of the transmission from 0 to 100%.
Hide Terminal
Click this button to toggle the Terminal Window at the bottom of the dialog.
Hide
Click this button to hide the dialog. Use the
Status
option in the Machine menu to show it again.
Stop
Click this button to stop the transmission. The following dialog will appear asking for confirmation.
Terminal Window
The Terminal Window shows the NC program being transmitted in plain text.
Options to
Scroll
the text or to
Show CR/LF
(Carriage Return/Line Feed characters) are located below the window.
Receive Status Dialog
The Receive Status dialog is mostly similar and functions the same as the Transmit Status dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.