# 官方语料摘录 D_setup_controls（共 39 页，源自 docs.cimco.com/en/docs/edit/2026/）


======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-helpeditor-help/
TITLE: Using Editor Help
======================================================================
PDF
Using Editor Help
Using Editor Help
This section describes how to use the help system in CIMCO Edit.
Help menu.
Editor help
The CIMCO Edit User Guide is available directly in CIMCO Edit as a standard Windows® Help file. You can open the help by going to the
Help
dropdown menu in the upper right corner of the editor and select
Editor help
.
If the help file is not available in your language, it will open the default English help file.
CNC-Calc help
Select this option to open the documentation for CNC-Calc.
Support info
Select this option to see who to contact for support.
Go to the CIMCO web site
Select this option to open the CIMCO web site in the default browser.
Connect to AI Agents...
Select this option to connect CIMCO Edit to an AI agent, so that the agent can work in CIMCO Edit. See
Connect to AI Agents
. The option needs the Ultra license.
About
Select this option to open the
About
dialog.
Using Help in Dialogs
Many dialogs throughout CIMCO Edit has a built-in help feature that provides information about specific options and fields.
Look for a question mark icon in the top-right corner of a dialog. Clicking it allows you to then select any option or field to view a brief explanatory note near your cursor.
You can also display the note for a dialog item by clicking in the field and then pressing the F1 key.
Question mark and curser.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-helpeditor-help/connect-ai-agents/
TITLE: Connect to AI Agents
======================================================================
PDF
Using Editor Help
Connect to AI Agents
Connect to AI Agents
An AI agent connected to CIMCO Edit can work in the CIMCO Edit you have open. It can read and edit NC programs, run backplot and machine simulation, and look into machine types and machines. You see everything it does.
CIMCO Edit connects itself to Claude (the Claude desktop app and Claude Code) and to Codex. Other AI agents can connect CIMCO Edit themselves, with a message that CIMCO Edit gives you.
Connect to AI Agents needs the CIMCO Edit Ultra license. Without it, the command is not in the
Help
menu.
Connecting an agent
Click the
Help
dropdown in the upper right corner of the Ribbon and select
Connect to AI Agents...
.
Connect to AI Agents dialog.
The dialog lists the AI agents installed on this computer. Each one shows whether it is connected. Click an agent to connect it. CIMCO Edit adds itself to the agent's configuration and leaves the rest of the configuration as it is.
When the Claude desktop app is running, connecting it closes Claude and starts it again, which ends what it is doing.
When the connection is made, start a new session in the agent, or restart it, to use CIMCO Edit. When CIMCO Edit cannot connect an agent by itself, click
Show the guide
in the message to see how the agent can connect CIMCO Edit.
Details
shows what was changed in each configuration file.
Another AI agent
Click this button to connect an agent that is not in the list. CIMCO Edit opens a page in your web browser with a message to give the agent, so that it connects CIMCO Edit itself. Copy the message to the agent, then restart the agent. A chat in a web browser cannot connect to CIMCO Edit. When no agent is installed, the button is called
An AI agent
.
When CIMCO Edit starts
When an AI agent is installed but not connected, CIMCO Edit asks once at startup whether to connect it. Click
Connect
to connect it, or
Not now
to skip it. Each agent is only offered once, so use
Connect to AI Agents...
to connect it later. Select
Don't ask again
to stop the question for all agents.
What the agent can do
The agent works in the CIMCO Edit you have open, and starts CIMCO Edit when it is not running. It can:
read and edit the open NC programs (each edit can be undone, and nothing is saved until a command saves it)
run the commands of the Ribbon and the menus, and use open dialogs
take screenshots of the CIMCO Edit window
run backplot and machine simulation, and check the toolpath
read and change machine types, the tool setup and tool libraries
write and run NC Function scripts
The agent cannot send or receive programs to and from CNC machines, or delete programs from the NC-Base database. The commands of the
Transmission
,
DNC-Max
and
NC-Base
tabs are not available to it.
Only the Windows user who started CIMCO Edit can connect an agent to it, on the same computer. The agent sees the open programs, their file paths, machine types and screenshots of the CIMCO Edit window, and sends them to its AI service. What the AI service does with the data depends on the agent.
Disconnecting an agent
CIMCO Edit has no command to disconnect an agent. Remove the entry
cimco-edit
from the agent's configuration:
Claude Code: run
claude mcp remove --scope user cimco-edit
Codex: run
codex mcp remove cimco-edit
Claude desktop app: close Claude, then delete
cimco-edit
under
mcpServers
in _claude_desktop
config.json
(in Claude,
Settings
>
Developer
>
Edit Config
)
The first time CIMCO Edit changes a configuration file itself, it keeps a copy of the file with the extension
.cimcoedit.bak
next to it.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/
TITLE: Editor Setup
======================================================================
PDF
Editor Setup
Editor Setup
This section describes the configuration options in CIMCO Edit.
Subsections
General
File Types
Global Colors
External Commands
Mazatrol Viewer
Machine Models
Custom Machines
Plugins
The Editor Setup dialog consists of two main areas. On the left, you will find the navigation menu that allows you to access different sections. On the right, the configuration settings for the chosen section are displayed.
Use the search bar at the top of the navigation menu to quickly filter through the sections.
At the top of the dialog, you can use the
icon to get information about most options. Simply click the icon and then click on an option to see a short description.
Setup dialog.
General Dialog Buttons
At the bottom of the Editor Setup dialog you will find the following buttons.
Export
Click this button to export the entire CIMCO Edit configuration to a .zip file. This can be used as a backup or for setting up CIMCO Edit on other PCs.
Import
Click this button to import a configuration. Please note that you will need to restart CIMCO Edit to apply the new configuration.
Help
Click this button to open the
Help dialog
.
Default
Click this button to reset CIMCO Edit to its default settings.
Cancel
Click this button to close the Editor Setup dialog without applying any changes.
OK
Click this button to close the Editor Setup dialog and apply the changes you have made.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/custom-machines/
TITLE: Custom Machines
======================================================================
PDF
Editor Setup
Custom Machines
Custom Machines
The
Custom Machines
section allows you to create, configure and manage custom machine configurations.
Subsections
Advanced Machine Editor
Machine Configuration Editor
Custom Machines dialog.
List of Machines
This section lists all available custom machines.
Advanced Edit
Click this button to open the
Advanced Machine Configuration Editor
for the selected machine.
Edit
Click this button to open the
Machine Configuration Editor
for the selected machine.
You can also create new machines directly using this editor.
Delete
Click this button to delete the selected machine.
Add
Click this button to add a new machine. The following dialog will appear:
Machine name:
The name of the new machine
Type:
Select number of axes and rotational setup:
3-Axis:
three linear axes
4-Axis Head:
adds a rotational axis to the head
4-Axis Table:
adds a rotational axis to the table
5-Axis Head / Head:
adds two rotational axis to the head
5-Axis Head / Table:
adds a rotational axis to the head and table
5-Axis Table / Table :
adds two rotational axis to the table
These settings can also be changed in the editor afterwards if needed.
After clicking the
OK
button the
Advanced Machine Configuration Editor
will open where you can begin to configure the new machine.
The 'Advanced' part of the editor's name refers to its ability to create most of the setup automatically for the user.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/custom-machines/advanced-configuration-editor/
TITLE: Advanced Machine Configuration Editor
======================================================================
PDF
Editor Setup
Custom Machines
Advanced Machine Editor
Advanced Machine Configuration Editor
The
Advanced Machine Configuration Editor
provides an efficient and intuitive interface for configuring different types of machine configurations. The 'Advanced' part of its name refers to its ability to create most of the setup automatically for the user.
With this editor, you have the advantage of visualizing the machine in real-time as you apply configurations, simplifying the process of observing the effects of modifications. It also automatically calculates the machine kinematics, adapting to the configured axes arrangement.
While this editor is designed for ease of use and will suit most needs, it is not capable of configuring complex features like collinear axes, revolvers, and spindles. These setups can be achieved using the
Machine Configuration Editor
.
Advanced Machine Configuration Editor dialog.
The editor is structured with a settings panel on the left for configuration options and a machine preview on the right that visually reflects changes in real-time.
You can right-click anywhere in the preview to change or reset the view.
Settings Panel
The settings panel contains the following sections:
Properties
This section contains general settings, including the machine's name, type, unit system, and the configuration of axes for both Head and Table components.
Models
This section contains a list of STL models with axes assignment, model color and visibility. Click the (+) sign to add an STL model.
Axes
This section lists the axes as defined by the machine type. You can set the
Travel limit
(min/max),
Feedrate
and
Position
for each axes.
You can preview the movement of the associated STL model with the axis. Clicking the play button animates the
Position
back and forth within the min/max
Travel limit
.
Tool Change Positions
This section defines the sequence in which the machine's axes move towards the tool change location. Each axis is set by choosing its order (1st, 2nd, 3rd, etc.) and the target position.
The movement begins with the axis labeled
1st
, followed by
2nd
, and continues in this manner, providing precise control over the machine's motion.
NC-Commands
Use this field to inject and execute an NC code when a tool change occurs.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/custom-machines/configuration-editor/
TITLE: Machine Configuration Editor
======================================================================
PDF
Editor Setup
Custom Machines
Machine Configuration Editor
Machine Configuration Editor
The
Machine Configuration Editor
provides a clean and intuitive interface for configuring different types of machine configurations.
It enables users to add geometry to individual machine component and specify the machine's axis components, movement limits, feedrates, and the tool change location. Additionally, it supports complex configurations such as collinear axes, revolvers, and spindles.
The layout of the editor is divided into three sections: a list of machines on the left, the configuration of components and axes at the center, and the properties section on the right.
Main configuration window.
In addition, the editor includes the
Machine Preview
(accessible via the
Preview
button). You cannot see the preview while editing a configuration, but for an improved experience, you can resize the preview to a smaller scale and place it beside the main editor window. The preview maintains its size and appear in the same location each time you click the
Preview
button.
Machine Preview window.
List of Machines
List of Machines
This field shows a list of all machine configurations.
Select a machine to see its configuration in the center section. The buttons below the field also apply to the selected machine configuration.
Right-click menu contains options for creating, saving and deleting machine configurations.
New
Click this button to add a new machine configuration.
Duplicate
Click this button to make a copy of the selected machine configuration.
Save
Click this button to save the selected machine configuration.
If the machine icon is red, this indicates there are errors that need resolving before you can save. A green icon indicates that the configuration is error-free and ready for its initial save.
Machine configurations are saved in the directory:
\AppData\Roaming\ ... CIMCO Edit install dirs ... \MachineCfg\
Delete
Click this button to delete the selected machine configuration.
Component and Axes configuration
Machine configurations use a hierarchical tree structure to represent the relationship between components.
Select any component to see its properties on the right side of the dialog.
The four buttons at the bottom of the dialog can be used to add geometry, add a linear or rotational axis, or to delete a component. The buttons are activated to reflect the options available for the selected component, but does not include all options available.
Instead, you can right-click any component to see
all
the available options, including additional options for
Add Collinear Axis
,
Add Spindle
and
Add Turret
.
Base
The
Base
component serves as the foundation of the machine. It is the root component of the
Head
,
Table
,
Tool Changer
, and other components.
Base
contains the following properties:
Name:
Name of machine configuration.
Unit System:
The Unit System (Metric/Imperial) used in the configuration for property values such as positions, limits and feedrates.
Orientation:
Use this setting to specify the orientation of the machine configuration.
Maximum Cutting Feedrate:
Defines the highest allowable cutting speed at which the tool moves through the material. Measured in millimeters per minute (mm/min).
Acceleration:
The rate at which the machine's axes can change speed. It determines how quickly the machine can reach its maximum feedrate or decelerate to a stop. Options include: Slow, Medium and Fast.
Work Origin:
Default position on the machine where Workpiece, Fixture, and Stock will be placed. Defined relative to the machine zero position (spindle nose).
Home Position:
The Home Position refers to the location defined by G53 (ISO) or M91 (Heidenhain). It is common practice to offset the machine STL files so that this position aligns with (0,0,0) in the coordinate system.
Head
The
Head
component represents the head of the machine where the spindle and tool holder are located. In the editor, it functions primarily as a structural element, providing a container for the child components (axes and geometry) that define the head's configuration.
Table
The
Table
component represents the table of the machine where the workpiece is secured. In the editor, it functions primarily as a structural element, providing a container for the child components (axes and geometry) that define the table's configuration.
Rotary Axis
A
Rotary Axis
represents an axis of rotation, defined by its orientation with respect to the X, Y, and Z axes. It provides a pivot point around which the machine components can rotate.
Contains the following properties:
Address:
Select a rotary axis A, B or C.
Limits:
Minimum and maximum travel limit values in degrees.
Feedrate:
The maximum feedrate to be used in rapid movements. For a rotary axes this must be defined in degrees per minute (deg/Min).
Direction:
This is set automatically, but can be adjusted if necessary. Defines the direction around which the axis will rotate.
Center:
Defines the X, Y, Z origin for the axis of revolution.
Linear Axis
A
Linear Axis
represents a linear axis in X, Y or Z along which the machine components can move.
Contains the following properties:
Address:
Select a linear axis X, Y or Z.
Limits:
Minimum and maximum travel limit values. The values must always be relative to the position of the axes when set to their machine zero position.
Feedrate:
Input the feedrate of the axis. This is the maximum feedrate to be used in rapid movements. For linear axes this value will need to be in millimeters per minute (mm/Min).
Direction:
Automatically set but can be adjusted if necessary. Defines the direction in which the axis will move along.
Collinear Axis
A
Collinear Axis
can be used to define multiple axes that are oriented in the same direction. It can be used in situations where several moving parts must be aligned along a common line.
Contains the following properties:
Address:
Select a linear axis U, V or W.
Limits:
Minimum and maximum travel limit values. The values must always be relative to the position of the axes when set to their machine zero position.
Feedrate:
Input the feedrate of the axis. This is the maximum feedrate to be used in rapid movements. This value will need to be in millimeters per minute (mm/Min).
Direction:
Automatically set but can be adjusted if necessary. Defines the direction in which the axis will move along.
Geometry
The
Geometry
component represents an STL model. Any component (Base, Head, Table, Axes, Tool Changer) can have multiple
Geometry
components added. A
Geometry
component will follow the movement and rotation of its parent component.
Contains the following properties:
File Path:
The path to the STL model file. Model files are copied to the configuration directory after saving and exiting the editor.
Unit System:
The measurement unit system used in the STL model. A wrong unit system will result in the STL model's scaling not being correct.
Color:
The color of the model represented in RGB with a value between 0-255.
When creating your own models, the geometry (CAD Model/STL models) of a machine must be set in relation to the machine zero position and the origin set to the tip of the spindle nose.
Tool Changer (Chain)
The
Tool Changer (Chain)
component defines the sequence in which the machine's axes move towards the tool change location. Each axis is set by choosing its sequence (order) (1st, 2nd, 3rd, etc.) and the target position.
The movement begins with the axis labeled 1st, followed by 2nd, and continues in this manner, providing precise control over the machine's motion.
Contains the following properties:
Sequence:
Defines the sequence in which the axis will move.
Position:
Defines the position on the axis.
NC-Commands:
Use this field to inject and execute an NC code when a tool change occurs.
Tool Changer (Turret)
The
Tool Changer (Turret)
component defines a rotating tool-holding component that allows for rapid switching between multiple different cutting tools. It is also sometimes referred to as a
revolver
.
Contains the following properties:
Mount Axis:
Defines which direction is up on the turret.
Direction:
The revolution axis of the turret.
Center:
The center of rotation for the turret slots.
Number of Slots:
Defines the number of slots in the turret. The individual slots are listed below this property.
Slot (1-64):
The position of an individual slot defined by X, Y, Z.
Tool Mount (Turret)
The
Tool Mount
component defines the configuration of the component on the turret (revolver) that securely holds the cutting tool in position.
Machine Preview
The
Machine Preview
shows the machine in 3D. You can navigate the simulation using rotate (click and hold left mouse button), zoom (mouse scroll wheel), and pan (click and hold right mouse button).
Additionally, you toggle the visibility of components (Head, Table, and Base) and test the travel limits of each axis using the
Axis Control
panel.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/external-commands/
TITLE: External Commands
======================================================================
PDF
Editor Setup
External Commands
External Commands
The
External Commands
section allows you to configure two external commands which can be executed directly from a menu in the
NC Functions
tab. External Commands are essentially command-line calls.
External Commands dialog.
External Command 1 and 2
Command Title
Use this field to specify a title for the External Command. An option to activate the External Command will be added to the
Commands
menu under the
NC Functions
tab. The text in this field will be used for this command.
Command program
Use this field to select the application that the command should execute. You can click the folder icon
to browse for the executable file.
Parameters
Use this field to specify the parameters for the command. These are the command-line parameters that will be appended to the executable selectd in the
Command program
field.
The following variables are available:
$FILE: Defines the file name without path.
$FILENOEXT: Defines the file name without extension.
$PATH: Specifies the path of the file.
$FILEPATH: Specifies the file name with path.
$OUTFILE: Name of the output file as defined below.
For example, to execute the command with the parameters:
-g C:\NCPRG\MOULD.NC C:\NCPRG\MOULD.NEW
enter the following:
-g $FILE $OUTFILE
and then, in the
Output file
field below, enter:
$PATH\$FILENOEXT.NEW
Wait for output from program
Check this field to wait for the external command to finish and open $OUTFILE if available, this locks the editor until the external command has finished running.
Output file ($OUTFILE)
Use this field to specify the name of the output file. The following variables are available:
$FILE: Defines the file name without path.
$FILENOEXT: Defines the file name without extension.
$PATH: Specifies the path of the file.
$FILEPATH: Specifies the file name with path.
See example above.
If no output filename is specified, it is assumed that the input file is modified.
Ribbon icon (.ico)
The icon of the command's button in the ribbon. Click the folder button to select an icon file (.ico). Leave the field empty to use the default icon. The icon is used in both the light and the dark theme, unless
Separate icon for dark theme
is checked. The disabled button is drawn from the same icon.
Separate icon for dark theme
Check this to select another icon file (.ico) in the field next to it, which the button uses when the dark theme is active. If that field is empty, the dark theme shows the default icon.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/
TITLE: File Types
======================================================================
PDF
Editor Setup
File Types
File Types
The
File Types
section allows you to manage File Types such as creating new ones, renaming, deleting and changing their order.
A File Type can be though of as a configuration profile for CIMCO Edit. It defines a set of rules and settings that tell the editor how to behave when you are working with a specific type of file.
It includes settings for visual aspects, like how program lines are color coded, to functional behaviors, such as block numbering, associated file extensions, load/save directories, file comparison, and recognizing machine-specific NC codes. It also defines the default control and machine to use when running a simulating and much more.
When you open a file, you can switch the editor to the appropriate File Type from the
File Type
menu under the
Editor
tab.
Please note that selecting a File Type means that the settings in the subsections, such as Colors, Block Numbers, Load/Save, and others, will be specific to that File Type. Look for the current File Type in the dialog header to see which one you are configuring.
Subsections
Colors
Block Numbers
Load / Save
File Compare
Machine
Backplot
Scanning
Multi Channel
Tool List
Other
CNC-Calc
Overview of File Types.
File types
File Types
This field displays the list of file types.
Use the Up/Down arrows
to move the selected file type up or down in the list. You can also use the sort button to alphabetically sort all file types.
Delete
Click this button to delete the selected file type. You will be prompted to confirm the delete operation.
Rename
Click this button to rename the selected file type.
Copy
Click this button to copy the selected file type.
Add
Click this button to add a new file type.
Add file type.
Enter the name of the file type, select one of the predefined templates to base the new file type on and click
OK
.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/backplot/
TITLE: Backplot
======================================================================
PDF
Editor Setup
File Types
Backplot
Backplot
The
Backplot
section allows you to configure the CNC control and machine configuration associated with the selected file type. This is also where you change the simulation version and export machine configurations.
The settings in this section only apply to the selected
File Type
. If you wish to configure a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Backplot dialog.
Backplot Setup
Control Type
Use this dropdown to select the CNC control for the selected file type.
The CNC control includes the configuration of the controller-specific syntax and commands, which are used to interpret and simulate the CNC program accurately.
You can configure the selected control, or other controls, by first selecting it here and then navigating to the
Control Settings
section.
Machine setup
Use this dropdown to select a specific machine configuration for the selected file type.
Click on the machine icon next to the dropdown to edit the machine configuration. This will open the
Machine Configuration Editor
.
Only custom machines can be edited.
Automatically import tools from a tool library
Select this option to automatically load tools from a specified library when starting simulation.
Tool Library
Use this dropdown to select the library from which tools should be automatically loaded.
You can see the tools (Assemblies, Cutters, Holders) that have been loaded in the
list of current tools
in the
Tool Manager
(upper section).
Highlight syntax errors when backplotting
Select this option to highlight errors in the program code when running a simulation (Backplot/Machine Simulation).
Simulation Window
Use this dropdown to select the the simulation version. CIMCO Edit includes two simulation engines; the
Standard version
and the new
Fast version
which is now the default engine. See
Simulation
for more information.
Enable enhanced quality (Beta)
Use this checkbox to enable or disable the new enhancing algorithm in the simulation. This option is enabled by default and is only available for
Fast version
(see option above).
Turning
Turning Configuration
List of orientation configurations. The default configuration will be selected unless a trigger is added to another configuration and this trigger finds the supplied text file.
Trigger
Use this field to set the trigger for the selected orientation configuration.
Orientation
Use this field to specify the orientation of the selected configuration.
Export
Export
Export the machine configuration as a .MacBundle file (Machine Bundle). The exported file can be used to import the machine configuration in CIMCO Edit on another PC.
When exporting, you will be asked to select the File Type. The control and machine configuration that corresponds to the selected File Type will be exported as part of the .MacBundle
Before exporting, please ensure the correct Control and Machine setup has been selected within the appropriate File Type.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/backplot/control-settings/
TITLE: Control Settings
======================================================================
PDF
Editor Setup
File Types
Backplot
Control Settings
Control Settings
The
Control Settings
section allows you to configure certain control specific parameters for the selected control and file type.
Changes to control parameters here are stored with the selected file type and does not overwrite the control configuration itself. This means you can have multiple file types that use the same control with different parameter settings.
Please see
Supported Controls
for more information about each control type.
Control Settings dialog.
Control Settings
Control Settings
Use the fields available to configure the selected control. When selecting a parameter, a description can be found at the bottom of the dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/block-numbers/
TITLE: Block Numbers
======================================================================
PDF
Editor Setup
File Types
Block Numbers
Block Numbers
The
Block Numbers
section allows you to configure line numbering for NC programs of the selected file type.
Block numbers serve as essential markers and are positioned at the start of each NC block. An NC program is primarily composed of these NC blocks, which sequentially outline the toolpaths necessary for machining a part.
CIMCO Edit helps ensure the integrity of these numbers during edits such as when adding new blocks. It also offers
Renumbering
features to restore proper line numbering after extensive changes.
The settings in this section only apply to the selected
File Type
. If you wish to configure block numbers for a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Block number configuration dialog.
Renumber Settings
Auto block numbering
Select this option to insert line numbers automatically based on the
Block format
settings in this dialog.
Upon inserting a new line, it will sequentially follow the number from the previous line, increasing by the chosen
Interval
.
If you add a new line in between other lines, its number will be halfway between the numbers of the line before it and the line after it.
Skip lines without block numbers
Select this option to skip lines without a block number when renumbering. The block number sequence is continued on the next line with a block number.
Renumber empty lines
Select this option to renumber empty lines such as a single empty line or several consecutive empty lines.
Disable standard renumbering
Select this option to disable the standard renumbering functionality for this file type. When using the
Renumbering
option under the _NC Functions tab, the
Advanced Renumbering
dialog will be shown instead.
Show quick setup
Select this option to show the following 'quick setup' dialog when using the
Renumbering
option under the
NC Functions
tab. This allows for swift configuration of the renumbering process.
Quick setup dialog
Disable undo prompt for large files
When attempting to renumber large files, a prompt will appear requesting to continue the operation which cannot then be undone. By selecting this option, the operation will be performed without showing the prompt.
Auto indent lines
Select this option to indent new lines. The indentation will be set at the same level as the line above.
Block format
Format
This field provides a list of available block number formats. Select a format from the dropdown list. For example, if you need block numbers with four digits (like 0001 up to 9999), you would pick the 0001 format.
Interval
Use this dropdown to select the interval by which the block number must increase for each block. Preset intervals are 1, 2, 5, 10, 20, 100, 1000 and Auto.
If you select one of the Auto options, the number selected is the
maximum block number
, and the interval will be selected to distribute the block numbers as evenly as possible, within this maximum block number.
For example, selecting
Auto 1000
for a CNC program with 482 NC blocks will distribute the numbers between 0 and 964 (which is the highest multiple of 482 that is less than 1000).
Block number character
Use this field to enter a character or string that will be inserted before the line number. For ISO type machines, this is normally the letter 'N'.
Start with
Use this field to specify the starting value of the block numbering.
Restart every
Use this field to specify when the line number must restart. This number is equal to the maximum line number. For example, to use line numbers from 0-9999, specify 9999 in this field. If no value is specified, the line number will increment until it reaches 100000000, before it restarts.
Alternate block number character
Use this field to specify an alternate block number character. For example, if the control uses both 'N' and ':' for block numbers, specify ':' in this field.
Start from line
Use this field to specify the first line in the program that will be given a line number.
Skip
Use this field to specify if block numbers should skip lines. For example, if you specify 2 in this field, only every 3rd line will be numbered.
Spaces after block number
Use this field to specify the number of spaces to insert after the block number. To insert block numbers with a specific column width, specify a negative value.
From line
Use this field to specify the number of lines that should be skipped before the renumbering begins.
To line
Use this field to specify the maximum number of lines that should be renumbered.
Positive number
If a positive number is entered, it specifies the last line to be renumbered, counted from the beginning of the program.
For example, if your CNC program starts with 4 comment lines and a program start line (with program start trigger and number, but without 'N'), only the first 10 NC blocks will be renumbered if you specify 15 in this field.
Negative number
If a negative value (-N) is specified, the last N lines (counted from the end of the program) will not be renumbered.
For example, if you specify the value -2, and the last line of your CNC program (line containing the program end code M30) is followed by another line containing a special character (e.g. %), then only the last line is not renumbered.
Skip lines starting with
Defines that lines starting with a particular string and/or characters should be omitted, i.e. '%', 'O', '(', etc. Multiple strings can be specified using a comma ',' as separator. If you wish to omit lines beginning with a comma ',', specify ',,'.
Restart on lines starting with
Use this field to specify when the block numbers should be restarted. For example, to renumber several programs in the same file, specify 'O' in this field, then the block numbers will be reset every time an O-Number is encountered.
Skip lines containing
Use this field to specify that lines containing a character or string should be omitted. Multiple strings can be specified using a comma ',' as separator.
Start renumbering from line containing
Use this field to specify a renumbering start trigger. If you specify a renumbering start trigger, renumbering will start from the first block containing the specified string. To start from the first block after the block containing the string, check the Start at next block option below.
Start at next block
Select this option to start renumbering from the block after the line containing the renumbering start trigger.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/colors/
TITLE: Colors
======================================================================
PDF
Editor Setup
File Types
Colors
Colors
The
Colors
section allows you to configure color settings for the selected file type.
This section can be accessed directly from the
File Type
menu under the
Editor
tab.
The settings in this section only apply to the selected
File Type
. If you wish to configure colors for a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Color setup.
Color Settings
Use colors
Select this option to use color highlighting.
Use colors in blocks
Select this option to use color highlighting for the text inside a selected block. When this is unchecked, the default color for
Text in blocks
is used.
Use modal colors
Select this option to use 'modal' colors. Blocks containing rapid moves, linear moves, and arcs will be assigned different colors.
If all three options above are unchecked, all text, including comments, will use the color defined in
Text color
.
List of colors
This list shows all the colors defined in CIMCO Edit.
Change a color by double-clicking its name in the list. You can also select a color and click the
button on the right side of the list.
Colors higher in the list have priority. If two colors are listed for the same text, the color that is listed first will be used. Use the arrow buttons to move the selected color in the list.
Colors in the list include:
Text color
The color used for text, when
Use colors
is not checked.
Background color
The background color used for editor windows.
Block color
The background color within a selection.
Comments color
The color used for comments, as defined by the Comment start and Comment end, or Block Skip character on the Machine template configuration tab.
Text in blocks
The color used in one or more selected program blocks when the field
Use color in blocks
is not checked.
Rapid moves
The color used for rapid moves.
Linear moves
The color used for linear moves.
Clockwise arcs (G2)
The color used for clockwise arcs.
Counter clockwise arcs (G3)**
The color used for counter clockwise arcs.
File compare background for different lines
The color used for the background for different lines.
File compare background for different text
The color used for the background for different text.
File compare color for missing lines
The color used for the background for missing lines.
Background color, Imported file
Highlighted line background color
The background color of the line where the curser is located.
Syntax error text color
The text color of syntax errors.
Syntax error background color
The background color of syntax errors.
Multi channel no lines background
The color used in sections with no lines.
Multi channel sync marker
The background color used for lines with sync markers.
Multi channel sync error
The background color used for lines with sync errors.
File compare difference wave
Select color
Select a new color. To select a new color, highlight a color in the list and click on this button (you can also double-click the color in the list).
Add new color
Click this button to add a new color. The field
Text
, at the bottom of the dialog will become active.
Enter the character or string of text that should have the new color
Select the options below the field that should apply to the color
Remove selected color
Click this button to remove the selected color.
Only user defined colors can be deleted.
Up/Down arrows
Use these buttons to move the selected color up or down the list. Colors higher in the list have priority.
Text
Use this field to specify a character or string of text that will be highlighted using the selected color.
Apply color to trailing digits
Select this option to apply the color to all digits following the matched character or string in the
Text
field.
Apply color to trailing letters
Select this option to apply the color to all letters following the matched character or string in the
Text
field.
Apply color to the entire line
Select this option to apply the color to the entire line.
Letter Colors
Click this button to create and insert a different color for each letter (A-Z).
By default, these colors will match the color scheme in CIMCO Edit V4.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/file-compare/
TITLE: File Compare
======================================================================
PDF
Editor Setup
File Types
File Compare
File Compare
The
File Compare
section allows you to configure the behaviour of the
File Compare
option.
The settings in this section only apply to the selected
File Type
. If you wish to configure a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
File compare dialog.
File Compare Settings
Single line step
Select this option to single step through multiple consecutive differences. Only the difference on the current line is highlighted.
Show all differences (No editing)
Select this option to show all lines with at least one difference. All the differences are highlighted at the same time.
Jump to next difference after sync.
Select this option to always jump to the next difference after you have synchronized two differences.
Use tab to switch window
Select this option if you want to use the tab key to switch between the two files being compared. You will not be able to insert tabs in any of the files when this option is enabled.
Mark Changes only
When you select this option, all the lines with at least one difference will be activated, but only the difference will be highlighted, not the entire line.
Use smart marking
When using this option, not only the different part of the command will be marked, but the complete command if it contains at least one difference.
Show minimap
Select this option to show the minimap for file comparisons.
Ignore Options
Ignore Block numbers
The values of block numbers will be ignored, as will the presence/absence of block numbers (i.e. the fact that there are block numbers in one file and not in the other will be ignored).
Ignore White spaces
White space characters will be ignored. White space characters are space (ASCII 32) and tab (ASCII 9).
Ignore Comments
Anything inside a comment will be ignored. For this to work, you must have specified the correct Comment start e.g. '(' and Comment end e.g. ')' characters for the
Machine
Template associated with the selected file type.
Ignore Case
If this option is checked, the letter case will be ignored, i.e. if one program contains lowercase and the other UPPERCASE characters for the same command.
Ignore Numeric format
Leading and trailing zeros will be ignored, as will optional '+' characters, i.e. 'X+14.10' matches 'X14.1', if this option is used.
Print Options
Print only differences
Select this option to only print the lines with differences between two files.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/load-save/
TITLE: Load/Save
======================================================================
PDF
Editor Setup
File Types
Load / Save
Load/Save
The
Load/Save
section allows you to associate file extensions, set default directories, auto save and more for the selected file type.
The settings in this section only apply to the selected
File Type
. If you wish to configure a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Load/Save dialog.
Load/Save
Default extension
Specify a default extension to use for the selected file type. This extension will be appended to any new files that are saved, unless an extension is specified in the
Save As
window.
Register default extension
Select this option to register the default extension(s) in Windows®. When an extension is registered in Windows®, clicking on a file with the specified extension in the Windows® Explorer will automatically open the file in CIMCO Edit.
Additional extensions
Define additional file extensions associated with your machine type. Extensions determine the type(s) of file(s) you wish to open (only files with the extension(s) defined here will be displayed in an Open file window). You can define more than one extension using a comma ',' as separator.
For example, to associate the extensions .ISO and .NC, specify ISO, NC.
Register additional extensions
Select this option to register the specified Additional extension(s) in Windows®. When an extension is registered in Windows®, clicking on a file with the specified extension in the Windows® Explorer will automatically open the file in the editor.
Default load path
This function specifies the default load path, which is where the file Open dialog will first point to. If no path is defined, the last directory you loaded a file from will be used. Click on the folder button
to browse for an adequate load path.
Default save path
This function specifies the default save path, which is where the file Save dialog will first point to, when you wish to save a new file of the selected type or when you use the file Save as menu. If no path is defined, the last directory you saved a file in will be used. Click on the folder button
to browse for an adequate save path.
Use separate load/and save directories
When this field is checked, the editor will remember the last load and save position independently.
Backup / Save
Auto save interval
Use this dropdown to select the length of the interval between auto saves. Auto saves overwrite the original file.
Save with linefeed type
Use this field to specify the linefeed type used when saving files.
Auto:
Do not change linefeed type. When saving new files, the DOS/Windows linefeed type is used.
DOS/Windows:
CR LF (ASCII 13 10)
Unix:
LF (ASCII 10)
Mac:
CR (ASCII 13)
UNICODE Files
Message when loading UNICODE
Displays a message when a UNICODE file is loaded.
Prompt to save files as UNICODE
Check this field if the file should be saved as UNICODE.
Always save files as UNICODE
Check this field if files should always be saved as UNICODE.
Always save files as regular text
Check this field if files should never be saved as UNICODE.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/multi-channel/
TITLE: Multi Channel
======================================================================
PDF
Editor Setup
File Types
Multi Channel
Multi Channel
The
Multi Channel
section allows you to configure how CIMCO Edit should identify multi-channel specific program codes for the selected File Type. It also provides options for the visual layout of channels in the editor and printing.
The Multi Channel option enables you to simultaneously view an NC program for machines with two or more channels. Channels are displayed side-by-side in separate editor windows, and the feature also incorporates the synchronization provided by Wait codes.
Channel windows can be synchronized with wait codes and editing can be done in all windows. Wait codes that match are shown in yellow and missing wait codes are shown in purple.
The settings in this section only apply to the selected
File Type
. If you wish to configure a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Subsections
Multi Channel Configuration
Multi Channel dialog.
Multi Channel View
Enable multi channel view
Check this field to enable Multi Channel view. If this is disabled, the options for multi-channel viewing in the
NC-Assistant
tab will also be disabled.
Print line numbers
Check this field to include line numbers when printing a program in multi-channel mode.
Show multi channel minimap
Select this option to show the minimap for multi channel synchronization.
Multi channel mode
Use this dropdown list to specify how to read the multi channel commands. You can either select one of the predefined types, or the
User Defined
type to manually define the multi channel commands using the fields below.
Channel start
Use this field to specify the Channel start command when multiple channels are stored in the same program file.
For instance, if you specify O as the Channel start command, CIMCO Edit will look for an O number at the beginning of each channel's section in the file. You can define multiple Channel start commands separated by commas to accommodate different starting points for each channel. For example, if the first channel starts with G13 and the second channel starts with G14, you would specify G13,G14 as the Channel start commands
Channel end
Use this field to specify the Channel end command when multiple channels are stored in the same program file. Please refer to
Channel start
for more details.
For example, enter M30 if each channel ends with M30. You can also specify the end of channel information using an advanced trigger / Regular Expression.
Channel order
Use this field to specify the order in which the channel windows should be displayed. Default is 1,2,3,4. To reverse the channels use 4,3,2,1 and so forth.
Configure
Click this button to open the
Multi Channel Configuration
dialog where you can configure synchronisation commands to a set of defined channels.
Test field
Use this field to test different commands such as
Channel start/end
and Synchronisation commands.
Save as template
Click this button to save the current configuration as a reusable template.
A dialog will appear where you can enter a name for the new template or choose to overwrite an existing one.
Load template
Click this button to load a template.
Template editor
Click this button to open the Template Editor.
For details about the available options, refer to this document and the information under the
Multi Channel Configuration
. The options in the Template Editor are identical to those described there.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/multi-channel/configuration/
TITLE: Multi Channel Configuration
======================================================================
PDF
Editor Setup
File Types
Multi Channel
Multi Channel Configuration
Multi Channel Configuration
The
Multi Channel Configuration
dialog allows you to configure the commands used to synchronisation channels in an NC program.
Multi Channel Configuration dialog.
Options
List of Synchronization Commands
This listbox displays all configured Synchronization Commands including their expression, Channel Number and Channel Number Trigger.
Add button:
Use the
Add
button below the listbox to add a new Synchronization Command which will simply add a blank entry in the list. Once you enter a an expression in the
Synchronization command
field below this will show up in the list.
Copy and Remove buttons:
Use the
Copy
and
Remove
buttons below the field to copy or delete the selected Synchronization Command. Note that CIMCO Edit will not ask for confirmation before deleting a Synchronization Command.
Synchronization command
Use this field to enter a string or
Regular Expression
that will identify a synchronization point/code in the NC program.
Basic Usage (String)
If synchronization points are indicated with !1, !2, etc., specify ! in this field. Make sure to select
String
from the dropdown button on the right side of the field.
Advanced Usage (Advanced)
If you need to specify the command using an advanced trigger (Regular Expression), you must add < > around the synchronization information to capture/extract it. Make sure to select
Advanced
from the dropdown button on the right side of the field.
Examples:
To synchronize on M300-M399, specify: M3<[0-9][0-9]>
To synchronize on all Pxxx, specify: P<[0-9]+>
Channel number trigger
Use this field to enter a string or
Regular Expression
(trigger) that will be used to identify channel numbers in the line from the
Synchronization command
field above.
Extract channel from line
Select this option to enable the
Channel number trigger
field above. This allows you to extract the channels to synchronize from the line identified in the
Synchronization command
field above.
Channel number
Use this field to enter the channel numbers to synch for the
Synchronization command
field above.
Examples
Macodel
Macodel example.
Synchronization command:
([^A-Za-z]?)M<9[0-9]{2}>($|[^0-9])
How the expression works:
Segment
Description
([^A-Za-z]?)
Ignores cases where any letter preceeds "M".
($|[^0-9])
Ignores cases where there is any numbers after.
<9[0-9]{2}>
Capture 9 followed by exactly two numbers between 0 and 9.
Channel number: 1,2
DMG Mori
Similar to Macodel, but with M100 to M199.
DMG Mori example.
Synchronization command:
([^A-Za-z]?)M<1[0-9]{2}>($|[^0-9])
Segment
Description
([^A-Za-z]?)
Ignore cases where any letter preceeds "M".
($|[^0-9])
Ignore cases where there is any numbers after.
<1[0-9]{2}>
Capture 1 followed by exactly two numbers between 0 and 9.
Channel number: 1,2
Star
Similar to Macodel and DMG Mori, but with M200 to M899.
Other M-Codes are not channel synchronization, they are for axis synchronization, these are not appropriate for multi-channel view, as these codes do not block program execution.
Star example.
Synchronization command:
([^A-Za-z]?)M<[2-8][0-9]{2}>($|[^0-9])
Segment
Description
([^A-Za-z]?)
Ignore cases where any letter preceeds "M".
($|[^0-9])
Ignore cases where there is any numbers after.
<[2-8][0-9]{2}>
Capture number between 2 and 8 followed by exactly two numbers between 0 and 9.
Channel number: 1,2
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/other/
TITLE: Other
======================================================================
PDF
Editor Setup
File Types
Other
Other
The
Other
section allows you to configure general settings for printing and exporting to DXF.
The settings in this section only apply to the selected
File Type
. If you wish to configure a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Other dialog.
General Settings
Print Columns
Use this dropdown to select the number of columns that should be used when CNC programs of the selected file type are printed.
Max line length indicator
Use this field to set the position of the Max line length indicator.
If you are using a proportional font (i.e. all letters are not the same width), the indicator does not show the exact line length.
Insert spaces when opening file
Select this option to automatically insert spaces when opening a file.
Export Toolpath as DXF File Settings
Always linearize arcs
Select this option to convert all arcs in the toolpath to a series of linear segments in the exported DXF file. This can be useful if the receiving system or software does not support arc interpolation.
Export turning toolpath in XY-plane
This setting is specific to turning operations. When you export a turning toolpath, this setting ensures that the toolpath is projected onto the XY-plane in the DXF file. This is important because turning typically involves movements in the XZ-plane, but for visualization and compatibility with certain CAD systems, you might need it on the XY-plane.
Arc quality tolerance
The allowable deviation from the ideal arc path when exporting a toolpath as a DXF file. It determines how closely the exported arcs need to match the original NC program's arcs.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/scanning/
TITLE: Scanning
======================================================================
PDF
Editor Setup
File Types
Scanning
Scanning
The Scanning option in CIMCO Edit is used to load and save information about the configuration of workpiece, fixture, work offset, tools, holders, geometry, and more, associated with an NC program. This information, known as
Scanning Commands
, can either be inserted directly in the NC program or stored in a separate file.
When starting simulation, CIMCO Edit performs a '
scan
' of the NC program or external file to locate and read the scanning commands. Following this, it is capable of loading, positioning, and setting up all the components within the simulation environment.
The Scanning feature is an invaluable tool for efficiency, allowing for the simultaneous loading of complete setups. Additionally, it facilitates the migration of setups from compatible CAD/CAM systems.
The settings in this section only apply to the selected
File Type
. If you wish to configure a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Scanning dialog.
The Scanning dialog consists of three sections:
Scanning Mode
,
Read/Write Settings
and
Placement of Tool Trigger
.
Scanning Mode
Scan for tool/holder/geometry information
Use this dropdown to select where CIMCO Edit should look for scanning commands about workpiece, fixture, tools, holders, etc.
Disabled:
Select this to disable Scanning.
Auto detect - prefer NC program file (always writes to NC program file):
Look for scanning commands in the NC program first. If nothing is found, look for a setup sheet (external .setup file). Always insert scanning commands in the NC program file.
Auto detect - prefer setup sheet (always writes to setup sheet):
Look for scanning commands in the setup sheet (external .setup file) first. If nothing is found, look for scanning commands in the NC program file. Always save commands in the setup sheet.
Always use NC program file:
Select this to always save scanning commands in the NC program file.
Always use setup sheet:
Select this to always save scanning commands in the setup sheet (external .setup file).
Read Settings (Load)
Read settings specify what scanning commands to read from either the NC program or setup sheet. The scanning and loading of elements and geometry is an automatic process when starting simulation.
Scan for tool information (type, diameter, length, ...)
Select this option to scan for tool information (type, diameter, length, ...).
Scan for holder information (type or profile)
Select this option to scan for holder information (type or profile).
Scan for stock information (bounding box, cylinder, STL, ...)
Select this option to scan for stock information (bounding box, cylinder, STL, ...).
Scan for work offsets
Select this option to scan for work offsets.
Scan for geometry information (holders and workpiece)
Select this option to scan for geometry information (holders and workpiece).
Scan for navigation information (active NC file only)
Select this option to scan for navigation information (active NC file only).
You need to enable this option for
Navigation
to work.
Write Settings (Save)
Write settings specify what scanning commands should be saved to either the NC program or setup sheet. Follow these steps to save:
While simulation is running, right-click anywhere in the
Geometry Manager
Select the option
Save Setup
Write tool information to NC file / setup sheet when saving setup
Select this option to write tool information to NC file / setup sheet when saving setup.
Write holder information to NC file / setup sheet when saving setup
Select this option to write holder information to NC file / setup sheet when saving setup.
Write stock information to NC file / setup sheet when saving setup
Select this option to write stock information to NC file / setup sheet when saving setup.
Write work offset information to NC file / setup sheet when saving setup
Select this option to write work offset information to NC file / setup sheet when saving setup.
Write geometry information to NC file / setup sheet when saving setup
Select this option to write geometry information to NC file / setup sheet when saving setup.
Placement of Tool Trigger
Placement of tool definitions
Use this dropdown to select where scanning commands should be inserted when saving the setup to the NC program file.
Top of file:
Insert all scanning commands at the top of the NC program file.
At tool change
Insert tool commands (definitions) before tool changes. All other scanning commands will be placed at the top of the NC program file.
Custom
Insert all scanning commands at the specified
Placement trigger
(see option below).
If the selected placement fails, the scanning commands are placed at line 1.
Placement trigger
Use this field to specify a placement trigger which is a unique string of text (a keyword). Upon locating this string within the NC program, CIMCO Edit will insert all scanning commands immediately following it.
Location of Setup Sheet
Use this dropdown to select where the Setup Sheet should be located.
Same folder as the program file:
Create Setup Sheet (.setup file) in the same folder as the program file.
Data folder:
Create Setup Sheet (.setup file) in the \CIMCOEdit\Data\ folder.
Custom folder (specify below):
Create Setup Sheet in a folder selected by the user (see
Custom folder
below).
Custom folder
Use this field to specify a folder path for the Setup Sheet. Use the folder icon next to this field to browse for a folder.
Scanning Commands
Scanning Commands are used for loading and defining elements such as workpiece, fixture, work offset, tools, holders, and more. These commands can be found within the NC program itself or within a separate Setup Sheet.
Below is a brief guide that outlines the general structure of some common Scanning Commands. Please note that this is not an exhaustive list of all the commands available.
For a practical understanding, we recommend conducting tests by saving the Scanning Commands to a copy of your NC program or to a Setup Sheet (.setup file). This hands-on approach will allow you to see the specific commands in action and understand their configurations.
The example below shows scanning commands in a Setup Sheet file.
TOOL 1 "LOLLIPOP MILL" HOLDER=H1 COMMENT="TOOL DESCRIPTION 1" AO0 BL40 CPI=T8 D10 FL20.5 US=UM AD10 SD2 SL30 TL0
TOOL 2 "END MILL" HOLDER=H1 COMMENT="TOOL DESCRIPTION 2" AO0 BL40 CD0 CR5 CPI=T8 EMCT=BEM D10 FL20.5 US=UM AD10 SD10 SL30 TL0
HOLDER BEGIN H1 "BT50" UM
69.85, 69.85, 3
100, 100, 12.5
100, 85, 4.33
85, 85, 6.34
85, 100, 4.33
100, 100, 7.3
HOLDER END
WORKPIECE ID1 "workpiece_1.stl" X0 Y0 Z0 A0 B0 C0 UM
WORKPIECE ID2 "workpiece_2.stl" X0 Y0 Z0 A0 B0 C0 UI RGB=127,127,0
FIXTURE ID1 "fixture_1.stl" X0 Y0 Z0 A0 B0 C0 UM
FIXTURE ID2 "fixture_2.stl" X0 Y0 Z0 A0 B0 C0 UM RGB=120,4,29
WCS ID0 X100 Y100 Z0
WCS ID1 X300 Y200 Z0
WCS ID2 X300 Y300 Z0
Fixture/Workpiece
The following scanning command is used for loading and positioning an STL model for a fixture or workpiece.
<TYPE> ID<ID> "<FILENAME>" X<NUMBER> Y<NUMBER> Z<NUMBER> A<NUMBER> B<NUMBER> C<NUMBER> <UNIT> <COLOR?>
Description of parameters
Param
Description
TYPE
Either of the two strings: FIXTURE or WORKPIECE
ID
Integer
FILENAME
Path to an ".stl" file
NUMBER
Integer, Float, X,Y,Z Coordinate or A,B,C Euler transformation
UNIT
Either of the two values: UM for Metric or UI for Imperial
COLOR
Optional parameter for color. RBG=<0-255>,<0-255,<0-255>. Defaults to 129,129,129 (gray)
Example of scanning command in either the NC program or the Setup Sheet.
WORKPIECE ID1 "workpiece_1.stl" X0 Y0 Z0 A0 B0 C0 UM
WORKPIECE ID2 "workpiece_2.stl" X0 Y0 Z0 A0 B0 C0 UI RGB=127,127,0
FIXTURE ID1 "fixture_1.stl" X0 Y0 Z0 A0 B0 C0 UM
FIXTURE ID2 "fixture_2.stl" X0 Y0 Z0 A0 B0 C0 UM RGB=120,4,29
Tool (Milling)
The following scanning command is used for loading/defining a tool.
TOOL <TOOL NUMBER> "<TYPE>" HOLDER=<HOLDER ID> COMMENT="<COMMENT>" <UNIT?> <DIMENSIONS>
Description of parameters
Param
Description
TOOL NUMBER
Integer with tool number
TYPE
String with tool type
HOLDER ID
Optional, Alphanumeric string [a-zA-Z0-9_-]
COMMENT
Optional, comment / description of tool
UNIT
Optional parameter with two possible values: UM for Metric and UI for Imperial
DIMENSIONS
List of tool dimensions
Please refer to the
Tool Scanning
section for further information about the tool scanning command and its associated dimension parameters.
Holder (Milling)
The following scanning command is used for loading/defining a holder for milling.
HOLDER BEGIN <ID> "<COMMENT>" <UNIT> FILE="<FILENAME>" 
<NUMBER>, <NUMBER>, <NUMBER> # Holder Segment: (Upper diameter, Lower diameter, Length of the segment) 
HOLDER END
Description of parameters
Param
Description
ID
Alphanumeric string [a-zA-Z0-9_-]
COMMENT
Optional, comment / description of holder. Must be encapsulated with double quotation marks
UNIT
Optional parameter with two possible values: UM for Metric or UI for Imperial
NUMBER
Integer, Float, Fraction
FILENAME
Optional. The path to an STL model to replace the holder. See
Tool Manager
for more information about Filename
Example of scanning command in either the NC program or the Setup Sheet.
HOLDER BEGIN H2 "B2C4-0011" 
42.9514,1.524,45.9994 
45.9994,6.0706,45.9994 
45.9994,2.00406,39.0652 
37.9984,4.0132,37.9984 
39.06012,2.00406,45.9994 
45.9994,3.1242,45.9994 
45.9994,1.27,43.4594 
22.225,3.175,15.875 
15.875,31.75,15.875 
15.875,1.4478,12.7 
12.7,5.334,12.7 
14.986,0.508,16.002 
16.002,11.43,16.002 
16.002,0.508,14.986 
HOLDER END
WCS (Work Offset)
The following scanning command is used for loading/defining the work offset.
WCS ID<INDEX> X<NUMBER> Y<NUMBER> Z<NUMBER> A<NUMBER> B<NUMBER> C<NUMBER>
Description of parameters
Param
Description
INDEX
Integer referring to the work offset index. (Currently we support 7 different work offsets (0-6))
NUMBER
X, Y, Z, A, B, C coordinate. Integer or Float
Example of scanning command in either the NC program or the Setup Sheet.
WCS ID1 X0.000 Y0.000 Z99.000 A0.000 B0.000 C0.000
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/scanning/navigation/
TITLE: Navigation
======================================================================
PDF
Editor Setup
File Types
Scanning
Navigation
Navigation
The
Navigation
section allows you to configure the structure and what keywords to
scan
for and show in the Navigation tab.
During the simulation of an NC program, the Navigation tab offers a well-organized overview (a tree menu) of the program's contents. This feature facilitates quick and effortless pinpointing of corresponding positions in both the NC program and the Navigation tab.
Please see
Navigation tab
for information about how to use Navigation.
To activate Navigation, you must first enable the option 'Scan for navigation information' found within the
Scanning
section of the Editor Setup.
The settings in this section only apply to the selected
File Type
. If you wish to configure a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Navigation dialog.
Navigation scanning settings
Path to current template
Shows the path to the file containing the current navigation template.
Load
Locate and load a navigation template.
Save As
Save the navigation tree structure.
Setup structure
Shows the keywords that CIMCO Edit will scan for within the active NC program and how they should be structured within the
Navigation tab
.
Add
Click this button to add a keyword to the navigation tree, note that the structure only permits a single child node under each branch, with a depth limit of 8 levels. By selecting the 'Add' button, you will append a new child node directly below the currently deepest nested level.
Rename
Click this button to rename the selected keyword. You can also double-click the keyword to rename.
For Navigation to work, you have to rename the levels to match the word(s) you want to 'scan' for in the NC program. You can only scan for words within comments in your NC program. You might have:
TOOL CHANGE
OPERATION
Depending on the NC program, the resulting structure in the Navigation tab might look like:
TOOL CHANGE
- T1 ENDMILL
OPERATION
1
OPERATION
2
OPERATION
3
OPERATION
4
TOOL CHANGE
- T2 BALL
OPERATION
5
OPERATION
6
OPERATION
7
OPERATION
8
It is important to note that you can only scan for words within comments in your NC program.
Remove
Click this button to remove the selected keyword.
If no template path has been specified, you will be asked to save changes to the setup structure when closing the dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/scanning/tool-scanning/
TITLE: Tool Scanning
======================================================================
PDF
Editor Setup
File Types
Scanning
Tool Scanning
Tool Scanning
The
Tool Scanning
section allows you to configure the format of the Scanning Command used for loading both milling and turning tools. This is the format CIMCO Edit will
scan
for in the NC program or Setup Sheet file when starting simulation and also the format it will use when saving a setup and Scanning Commands.
The Scanning Command for a tool contains several letter codes such as AO, BL, CPI, etc. These are referred to as
Keywords
and define different aspects of a tool such as Shaft Diameter (AD), Body Length (BL) or Cutter Point Index (CPI). If required, the naming of some of these keywords can be changed.
Please refer to the
Scanning
section for more information about Scanning Commands and how they are used in CIMCO Edit.
The dialog has two variations with one set of options for milling tools and another for turning tools. Which one is shown depends on what
Control Type
is selected for the current
File Type
and the
Control Type
is set in the
Backplot
section. However, any changes made in the Tool Scanning dialog will be associated (saved) with the selected
File Type
.
The settings in this section only apply to the selected
File Type
. If you wish to configure a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Tool Scanning dialog (Milling tool).
Automatic tool scanning (milling)
Tool line trigger
Use this field to enter the string that identifies a line as a tool.
Tool type
Use this dropdown to select a tool type and see/update its parameter name in the field below. The
Tool dimension keyword
dropdown will also update with the keywords available for the selected tool type.
Tool dimension keyword
Use this dropdown to select a tool dimension and see/update its keyword in the field below.
Example
This fields shows an example of the resulting Scanning Command.
Tool Scanning dialog (Turning tool).
Automatic tool scanning (turning)
Tool line trigger
Use this field to enter the string that identifies a line as a tool.
Assembly type
Use this dropdown to select an Assembly type and see/update its keyword in the field
Assembly keyword
. All other fields and dropdowns will also update to show the parameters and keywords available for the selected Assembly type and its components.
Assembly keyword
Use this field to enter a keyword for the selected Assembly type.
Assembly parameter
Use this dropdown to see a list of parameters available for the selected Assembly type. The associated keyword is shown in the field on the right (cannot be changed).
Holder
Use these fields to select a holder and see its parameters and keywords. These cannot be changed.
Cutter
Use these fields to select a cutter and see its parameters and keywords. These cannot be changed.
Example
This fields shows an example of the resulting Scanning Command.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/setup-machine/
TITLE: Machine
======================================================================
PDF
Editor Setup
File Types
Machine
Machine
The
Machine
section allows you to configure machine specific program characters, NC codes, units and other machine related settings associated with the selected file type.
The settings in this section only apply to the selected
File Type
. If you wish to configure a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Machine type dialog.
Special Characters
Comment start
Use this field to enter the comment start character. For example (.
Comment end
Use this field to enter the comment end character. For example ).
Block skip
Use this field to enter the block skip character. If you do not want a block skip character, just leave the field empty.
Decimal point
Use this field to enter the decimal separator (decimal point or comma).
Use decimal point on numeric keypad
Select this option if the decimal key on the numeric keypad should insert the decimal point specified above.
Block skip after block number
Select this option if a block skip should be inserted after the block number. If you leave this field unchecked, the block skip will be just before the block number.
You can specify another block skip character in the field
Block Skip
, if necessary.
Enable multi line comments
Select this option to enable coloring of multi-line comments.
Multi-line comment start
Use this field to specify the multi-line comment start string.
Multi-line comment end
Use this field to specify the multi-line comment end string.
NC Codes
Tool Change
Use this field to specify the tool change prefix.
For example, if the tool number is specified as T010101, specify T in this field.
Tool load
Use this field to specify the tool load command. If the tool load command is found on the same line as the tool change command, the tool is loaded immediately.
For example, N1230 T020202 M6.
Set feedrate
Use this field to specify the feedrate prefix.
For example, if the feedrate is specified as F1000, specify F in this field.
Set spindle speed
Use this field to specify the spindle speed prefix.
For example, if the spindle speed is specified as S1000, specify S in this field.
Units
These settings
Decimals
Use this field to specify the number of decimals shown in the backplot/simulation etc.
Rapid speed (mm / min)
Use this field to specify the default rapid feedrate.
Toolpath unit
Select the toolpath measurement unit. This is used throughout CIMCO Edit including within the backplot/simulation etc.
Feedrate unit
Use this field to specify the default feedrate unit.
Treat higher feed G1 as rapid
Treat cutting moves with feed higher than rapid feedrate as rapid moves.
Use machine setup feedrates
Use machine setup feedrate as rapid feedrate.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/setupfiletypes_cnc_calc/
TITLE: CNC-Calc
======================================================================
PDF
Editor Setup
File Types
CNC-Calc
CNC-Calc
Use this dialog to configure CNC-Calc settings
Turning
Check this field to simulate 2D turning (Lathe) programs.
Diameter programming
Check this field to select diameter programming.
Number of decimals
Use this field to specify the maximum number of decimals in coordinates etc.
Maximum arc output angle
Use this field to specify the maximum angle of the arcs in the generated NC program.
Spline substitution tolerance
Use this field to specify spline substitution tolerance.
Selected Post Processor
Use this to select the Post Processor that the output should be formatted for.
Open
Open Post Processor manual (PDF).
Show grid
Use this check box to specify if the grid should be shown.
Grid size
Use this field to specify the distance between grid points.
Show sub-grid
Use this field to specify if the sub grid should be shown.
Show origin
Use this check box to specify if axis should be shown.
Axis substitution name
Use this field to specify axis substitution name.
Axis substitution tolerance
Use this field to specify axis substitution tolerance.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/toollist/
TITLE: Tool List
======================================================================
PDF
Editor Setup
File Types
Tool List
Tool List
The
Tool List
section allows you to set up tool list triggers and configure the layout of tool lists.
The settings in this section only apply to the selected
File Type
. If you wish to configure a different File Type, go to the
File Type
section, change the type, and then revisit this section to continue. You can see the current File Type at the top of the dialog.
Tool List dialog.
Tool List Setup
Use advanced configuration template for tool lists
Check this field to use the advanced tool list generator that offers a wider range of customization options for tool lists, including both HTML and XML formats.
For more information, please refer to the information in the default template file. When selecting this option the
Tool list template
field (below) will display the location of the template file.
Click on the
Edit tool list template
button (
) to open the template and follow the instructions described within the file.
Please see the section
Advanced Configuration (HTML Tool List)
below for an example of how to create a HTML based tool list.
Tool trigger
Use this field to specify the tool trigger for the selected File Type. This is the character or string that CIMCO Edit will match and identify as a tool in the NC program.
For instance, if your machine uses T01 for tool 01, specify T in this field.
You can also use a Regular Expression by clicking the icon on the right side of the field and selecting
Advanced
. See
Regular Expressions
for more information.
$TOOL1 / $TOOL2 Trigger
Use these fields to specify the advanced trigger that should be used to generate the $TOOL1/2 variable.
For example, to include the value specified after R in the following line:
T1 5MM DRILL R33
Specify the trigger R<[0-9]+>.
This will assign the value R33 to the $TOOL1 variable.
Filter comments with advanced trigger
Use this field to specify the advanced trigger (Regular Expression) that should be used to filter (scan) comments. Comment lines are only used if they match the Regular Expression and, by default, CIMCO Edit looks for comment lines above the tool trigger/code.
The comment filter is useful when each tool is surrounded by multiple comments as in the example below:
(********************)
(* BALL MILL D6 *)
(********************)
T3
If you use the default configuration, CIMCO Edit will extract the following information:
T3 ********************
To get the correct tool description, you can add the following Regular Expression:
[A-Z0-9 ]+
This ensures that the tool comment includes letters, numbers and spaces. The tool list will then shown:
T3 (* BALL MILL D6 *)
Sort tool list
Select this option to sort the tool list and only list each tool once.
Ignore duplicate info (T020202 = T02)
Select this option to ignore duplicate/magazine info in the tool number, i.e. T020202 should be listed as T02.
Ignore 0's (T02 = T2)
Select this option to ignore leading zeros in tool numbers, i.e. T02 should be listed as T2.
Two line comments
Select this option if the tool comment consists of two lines.
Scan comments below tool name
Select this option if the tool comment is always located below the tool change line.
Advanced Tool trigger: Scan two lines at a time
Select this option if the advanced tool trigger should scan two lines at a time.
Tool list template
Use this field to specify the path to the tool list template. Click the folder icon to the right
to select a tool list template.
Click the icon
next to the folder icon if you wish to edit the specified tool list template.
Advanced Configuration (HTML Tool List)
CIMCO Edit comes pre-installed with three tool list template files, located in: C:\Users\<user>\AppData\Roaming\CIMCO 2026\CIMCOEdit\SYS
Toollist.txt:
- Simple tool list template
NewToolList.txt:
- Advanced tool list configuration template
NewToolListHtmlSample.txt:
- Example of advanced tool list with HTML output
To create your own HTML tool list, we recommend starting by making a copy of the template file: 'NewToolListHtmlSample.txt'. Rename the copied file to something meaningful that reflects its purpose.
Before configuring the file, navigate to
Setup
>
File Types
and select the
file type
where you want the custom tool list to be applied. Once selected, return to the
Tool List
dialog.
To use the new HTML tool list, configure the dialog the following way:
Enable the option
Use advanced configuration template for tool lists
.
Tool Trigger
field: Enter any value here. This field is not used for HTML lists, but must not be left empty — otherwise, an error will be shown indicating the tool list is not configured.
Tool List Template
: This field should point to the full path and filename of your custom HTML template.
Configuration example
Inside the copied template file, you’ll find two main sections:
The first part, between [CONFIG_BEGIN] and [CONFIG_END], contains the configuration settings that control how tool data is extracted and interpreted.
The second part, beginning with the [HEADER_BEGIN] section, defines the HTML structure used for generating the tool list output.
LOCK_CONFIGURATION=Yes
In the configuration section, set this to 'Yes' to ignore configuration options from CIMCO Edit. The default is 'No'.
In the following we will work with this example code.
T="MILL DIAMETER 16"
;C635571 (TOOL ARTICLE SAP CODE)
;2-FLUTE MILL D16 (TOOL DESCRIPTION)
;POHSS-45454 (TOOL HOLDER CODE)
;32 MM (TOOL PROTRUSION LENGTH)
;TEST1 (TEST VALUE 5)
;TEST2 (TEST VALUE 6)
;TEST3 (TEST VALUE 7)
TOOL_TRIGGER_REGEX=
Use TOOL_TRIGGER_REGEX to define a regular expression that identifies tool definitions in an NC program. This allows you to match specific patterns and extract tool information such as tool names or IDs.
Important: Ensure that the line TOOL_TRIGGER= is left empty.
To extract the tool name from a line like: T=”MILL DIAMETER 16”, use the following expression:
TOOL_TRIGGER_REGEX= T="([[:space:]0-9a-zA-Z/]+)"
This will capture the tool name "MILL DIAMETER 16" from the quoted string.
Next, to define which character marks the beginning of a comment in your NC program, use the following setting:
COMMENT_START= ;
By default, the comment character is set to '('. In this case, we set it to ';' because all comment lines in the program begin with a semicolon.
All tool-related comments identified by the system are stored in the variable $TOOLINFO. To include these comments in the generated HTML output, simply insert $TOOLINFO into your template. This will output all matching comment lines without the original comment symbol.
NUMBER_OF_COMMENTS= 7
If there are multiple comment lines following a tool definition, you must set NUMBER_OF_COMMENTS to match the total number of lines you want to capture. In this example, there are 7 comment lines.
To extract each comment into a separate variable, you need to define each line individually by repeating and adjusting the following section in your configuration file accordingly. This allows you to reference each comment line separately in your HTML output with variables $INFO1, $INFO2, etc.
[EXTRACT_FROM_TOOL_COMMENT_BEGIN]
#Name of variable (only $A-Z0-9 allowed)
VARIABLE= $INFO1
#Regular expression used to extract the text
EXTRACT_REGEX= ^([[:alnum:]-]+)[[:space:]]*\(TOOL ARTICLE SAP CODE\)$
[EXTRACT_FROM_TOOL_COMMENT_END]
To include an image in the HTML output, simply use standard HTML img syntax. For example:
<img src="Logo.jpg" alt="Logo" width="430" height="105" style="vertical-align:bottom" style="float:right">
Make sure the image file (e.g., Logo.jpg) is located in the same folder as your tool list template or accessible via a valid path.
To test the template, save your changes to the template file. Then open an NC file in CIMCO Edit and ensure the correct
File Type
is selected. Then go to the
NC Functions
tab and click the option
Make Tool List
. This will generate the HTML code output in a new file tab.
This will generate the HTML output in a new tab within CIMCO Edit. You can then save it with a .html extension and open it in a browser to view your tool list, complete with any images and formatting you’ve applied.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/general/
TITLE: General
======================================================================
PDF
Editor Setup
General
General
Subsections
Editor Settings
NC-Assistant
Printing
The
General
section allows you to configure general settings.
General program settings.
General Program Settings
Start maximized
Select this option to make the program window start maximized.
Remember window position
Select this option to make the programs start at the size and position where it was last opened.
Open windows maximized
Select this option to open files/documents maximized.
Warning beeps
Select this option to enable warning beeps. Note that this will not change the system sounds settings in Windows.
Protect read-only files
Select this option to prevent read-only files from editing.
Check external changes
Select this option to enable CIMCO Edit to monitor for any modifications made to files externally. Should a file be altered outside of the editor, you will be prompted with the choice to reload it.
Warn about access conflicts
When this option is checked, CIMCO Edit will warn you if another instance of CIMCO Edit opens a file that you have open. The other editor will also display a warning that you are using the file.
Only instances of CIMCO Edit trigger these warnings. This function relies on hidden files, so permissions must be either
Read
or
Full
. If CIMCO Edit can create but not delete files, hidden files will accumulate.
Open file multiple times
Select this option if you want to be able to open the same file in more than one window in the editor.
Hide 'Download Latest Version'
Select this option to hide the 'Download Latest Version' link from the Help menu. Note that you must restart the editor after changing this option.
Show new version reminder
Select this option to show a reminder on start up if a new version of CIMCO Edit is available.
Show full path in title
Select this option to show the full path of files in the window title.
Specify name when receiving
Select this option if you wish to specify a filename when using the Transmission tab option
Receive file and open in editor
.
Always show all files (*.*)
Select this option if the file dialog should always show all files.
Re-open files
Select this option to re-open files from the last session when the program is started.
Remember cursor position
Select this option to place the cursor at the position where it was when the file was last opened.
Confirm program exit
Select this option to always confirm when exiting.
Open files with wrapped lines read only
Select this option to have files containing lines longer than 1024 characters opened as read-only, this ensures that the files are not corrupted.
Open all files as read-only
Select this option to open all files as read-only to prevent editing.
Use 'Dark Mode' colors
Select this option to enable 'Dark Mode'.
Enable TRAUB WinFlex file parsing
When enabled, the Editor will attempt to detect and parse files exported from TRAUB CNC machines. These files are typically produced using TRAUB's WinFlex system and contain CNC program content such as .prg files along with related information.
Language
Use this dropdown to select the language to be used in CIMCO Edit. After changing language, the editor must be restarted.
The following languages are currently available:
Chinese
Czech
Danish
Dutch
English (US)
Estonian
Finnish
French
German
Hungarian
Italian
Japanese
Korean
Polish
Portuguese
Romanian
Russian
Spanish
Swedish
Taiwanese
Thai
Turkish
Tab width
Use this field to specify the tab width in characters.
Show file size in
Use this dropdown to select how the file size should be displayed in the status bar. The file size can be shown in bytes, in meter, or in feet.
Number of linefeed characters
Use this field to specify how many line feed characters that should be used to calculate the file size shown in the status bar.
Example:
If you specify a value of 2, and the file contains 12 lines, 24 bytes will be added to the file size shown in the status bar.
Default simulation window size
Use this field to change the default size of the simulation window in percent of the screen size. The default value is 66 %. Decrease this value to show NC files with long program lines, or increase the value to enlarge the simulation window.
You can resize the Backplot window between 10-90% of default value 66%.
Keyboard/ Mouse Mapping
Use this dropdown to select the keyboard mapping.
Recent list size
Use this dropdown to specify the number of files shown in the
Recent List
.
Save backup file
Select this option to backup the previous version of a file when saving. By default backup versions will get the extension .bak.
Backup Extension
Use this field to set the extension of backup files.
Exit editor and save files when inactive
Check this field to exit editor and save files when inactive, use the field
Minutes of inactivity before exit
to specify the duration before exit.
Minutes of inactivity before exit
Use this field to specify how many minutes of inactivity is needed before the editor is exited, all files is saved before exit.
Associate file extensions
Click this button to associate file extensions (
.NC,
.H, etc.) with CIMCO Edit, overwriting the current association.
When you click this button, CIMCO Edit re-associates all the extensions defined for each
File Type
under
Load/Save
.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/general/editor/
TITLE: Editor Settings
======================================================================
PDF
Editor Setup
General
Editor Settings
Editor Settings
The
Editor
section allows you to configure the general look and behaviour when editing documents such as NC programs.
Editor settings.
Editor settings
Keyboard acceleration
Select this option to enable the keyboard cursor to move faster.
Prompt when unable to undo
When this is enabled, you will be told when you are about to do something (such as renumbering a large file) which cannot be undone. If this is disabled, no warning will appear.
Vertical scroll bar
Select this option to enable a vertical scroll bar.
Horizontal scroll bar
Select this option to enable a horizontal scroll bar.
Disable Backspace at start of line
Select this option to prevent that lines are joined by using the backspace key.
Replace from top
Select this option to have search and replace options automatically start from the beginning of the file.
Replace tabs with space
Select this option to insert spaces when the tab key is used. This also replaces existing tabs with spaces when a file is opened.
Show line numbers
Select this option to show line numbers.
Show replaced count
Select this option to show the number of strings that were replaced after the
Replace all
function has been used.
Use virtual space
Allows the cursor to move into space with no text.
Pad with tabs
Select this option to use tabs to fill in large empty spaces in virtual space. (Please refer to
Use virtual space
above.)
Remove ASCII 0's
Select this option to remove ASCII 0's from the file. If this option is disabled, ASCII 0's are replaced with ASCII 128.
If you transmit files with 7 data bits, ASCII 128 becomes ASCII 0.
Wrap Searches
Select this option to have searches continue from the top of the file if no match is found before the end of the file.
Always UPPER CASE
Select this option to force UPPER CASE (all CAPS).
Remember math values
Select this option to remember the previous values used in the Simple Math Functions.
Highlight current line
Select this option to highlight the currently selected line in the editor.
Show Whitespace and TAB
Select this option to show whitespace and tabulators in the editor.
Show minimap in editor documents
Select this option to show the minimap in regular editor documents. This setting does not affect File Compare or Multi Channel minimaps.
Block Mode
Drag-and-drop text editing
Select this option to enable dragging of selected text.
Copy without selection
Select this option to copy the line at the cursor, without marking it as a selection.
Don't move cursor after paste
Select this option if you want the cursor to stay at the start of the text you have just pasted, instead of jumping to the end.
Mark to end of line
If a whole line is selected, the indication continues across virtual space to the side of the window.
Font settings
Preview field
This field shows an example of the selected font. Click the
Select font
icon
to change the font used in the editor window.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/general/nc-assistant/
TITLE: NC-Assistant
======================================================================
PDF
Editor Setup
General
NC-Assistant
NC-Assistant
The
NC-Assistant
section allows you to configure the general behaviour of the NC Assistant.
NC-Assistant settings.
NC-Assistant settings
Suppress NC-Assistant
Select this option to hide the NC-Assistant sidebar including macros. This option also disables the show/hide options under the
NC Assistant
tab
Show NC-Assistant suggestions on keyboard input
Select this option to enable NC-Assistant suggestions. A dropdown with NC-Assistant macro suggestions will appear as you type in the Editor.
Hide NC-Assistant formula results
Select this option if the result of NC-Assistant macro formulas should be hidden.
Allow NC-Assistant during Backplot
Check this option to allow the NC-Assistant sidebar while Backplot or Machine Simulation is active. When unchecked, the sidebar is hidden until Backplot or Machine Simulation is closed.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/general/printing/
TITLE: Printing
======================================================================
PDF
Editor Setup
General
Printing
Printing
The
Printing
section allows you to configure the size of paper, fonts, headers/footers, multi-column printing, etc.
Printer setup.
Print options
Syntax highlight
Select this option to apply syntax highlighting to the printed text. Use Bold and Italic to highlight NC commands and comments.
Use colors
Select this option to enable color printouts. This requires a color printer.
Print headers
Select this option to print headers on every page.
Print footers
Select this option to print footers on every page.
Print header on first page
Select this option to print a header on the first page.
Raw print
Select this option to produce simple text output to the printer.
This is useful when printing large programs to matrix printers. When raw print is selected, the options
Syntax highlight
,
Use colors
and
Print header on first page
will be disabled.
The options
Send form feed
,
Print on endless paper
,
Send form feed after last page
and
Paper height
will be enabled to setup the raw print.
Send form feed
When this option is enabled, a form feed character (FF) will be sent after reaching the
Paper height
counter, and the next line will be printed on the next page. No form feed character is needed after the last page, so the option
Send form feed after last page
will be disabled.
Print on "endless" paper
Select this option to print on endless paper. When selected, no header and/or footer is printed.
Send form feed after last page
When this option is enabled, a form feed character will be sent at the end of a raw print on continuous paper to indicate the last printed page.
Left margin / Right margin
Specify the size of the margins in centimeters. If the margins are in inches add "in" such as '1in'.
Paper width / Paper height
Specify the size of the paper in width and height of the paper in characters.
If for example in multi-column printing the font size is set to 11 points and the
Paper Width
is set to 35 (characters/line), a CNC program of 140 NC blocks will be printed legibly in two columns on an A4 page.
Normal printer font
Shows a preview of the font used for normal printing.
Click the icon
to select the font size and type for the printout.
Multi column printer font
Shows a preview of the font used for Multi colum printing.
Click the icon
to select the font used when printing in 2 or more columns.
Header/Footer
Header/Footer (Left, Center, Right)
Use these fields to specify the contents of the header and footer. The following options are available:
%p : Page number
%P : Page count
%f : File name
%F : File name with path
%t : Time
%d : Date
%c : Company name
%U : Windows user name
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/global-colors/
TITLE: Global Colors
======================================================================
PDF
Editor Setup
Global Colors
Global Colors
The
Global Colors
section allows you to configure general colors for the simulation versions and the CIMCO CNC-Calc add-on.
Global Colors dialog.
Global Colors
List of Colors
This field lists all the colors that can be configured. Select a color to change it using the sliders at the bottom of the dialog or double-click to use the
Color
dialog.
Select Color
Click this button to open the
Color
dialog where you can select from predefined colors or create custom colors.
Default
Click this button to change the selected color back to the default color.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/machine-models/
TITLE: Machine Models
======================================================================
PDF
Editor Setup
Machine Models
Machine Models
The
Machine Models
section is only visible when the Machine Simulation add-on is activated. The dialog allows you to conveniently download and install machines for use with Machine Simulation.
Machine Models dialog.
List of Machines
This section lists all the available machines that can be downloaded. Click the
Update
button to list machines or to reload the list.
To install a machine, enable its checkbox in the
Install
column and click the
Install
button at the bottom of the dialog. A similar approach is used for uninstalling or viewing a machine's release notes.
Description of columns:
Install:
Checkboxes to select machines
Name:
Name of machine
Status:
New:
Machine is not installed
Installed:
Machine is installed
Update:
Update available for installed machine
Version:
Machine version
Notes:
Machine version and latest note
Status
Will show the current status of the installation or update.
Check for updates at launch
Select this field to get a notification about updated machines when launching the CIMCO Edit.
View Notes
Click this button to view all modifications that have been made to the selected machine.
Update
Click this button to list machines or to reload the list.
Uninstall
Click this button to uninstall all the selected machines.
Install
Click this button to install all the selected machines.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/mazatrol-viewer/
TITLE: Mazatrol Viewer
======================================================================
PDF
Editor Setup
Mazatrol Viewer
Mazatrol Viewer
The
Mazatrol Viewer
section allows you to configure how Mazatrol files should be displayed and associate specific file extensions with Mazak CNC controls.
The Mazatrol Viewer only allows you to view and print Mazatrol binary files (without header information). It is not possible to make changes or save a file back to its original binary format.
The Mazatrol Viewer is an add-on for CIMCO Edit. It is purchased separately and requires a valid license. The Mazatrol Viewer add-on can be enabled under
Plugins
.
Mazatrol Viewer dialog.
Mazatrol Viewer
Language
Use this dropdown to select the language used when displaying the Mazatrol data.
Mazatrol Viewer Decimals
Use this field to specify how many decimals should be used to display values in the Mazatrol Viewer.
Show TPC Data
Select this option to include TPC data when viewing Mazatrol files.
Font settings
Preview field
This field shows an example of the selected font. Click on the font button to the right to select another font.
Associations
List of Associations
Use this field to associate specific file extensions with Mazak CNC controls. Use the buttons
Delete
,
Edit
, and
Add
to manage associations in the list.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/editor-setup/plugins/
TITLE: Plugins
======================================================================
PDF
Editor Setup
Plugins
Plugins
The
Plugins
section allows you to activate or deactivate certain options, modules, and add-ons. It also provides the option to secure the Editor Setup with a password and modify the paths for the default configuration directories.
CIMCO Edit must be licensed according to the plugins you wish to use in the editor.
Plugins dialog.
Select Plugins
Disable Backplot
Select this option to disable the backplot/simulation. This will remove the
Backplot
tab.
Backplot requires a CIMCO Edit Professional license.
Disable advanced simulation
Select this option to disable advanced simulation options such as solid simulation. This will remove the
Solid
menu under the
Backplot
tab.
Disable DNC/Serial communication
Select this option to disable the DNC/Serial communication module.
Requires a license for DNC-Option.
Disable File compare
Select this option to disable the File compare function. This will remove the
File Compare
tab.
Disable advanced NC-Functions
Select this option to disable the advanced NC functions. This will remove the
Tranform
and
Info
menus and their options under the
NC Functions
tab.
Advanced NC functions requires a CIMCO Edit Professional license.
Disable NC-Base
Select this option to disable the NC-Base Client (if installed along with NC-Base Server).
Requires an extended license for CIMCO Edit.
Disable DNC-Max Client
Select this option to disable the DNC-Max Client (if installed along with NC-Base Server and DNC-Max Server).
Requires an extended license for CIMCO Edit.
Disable CNC-Calc
Select this option to disable the CNC-Calc module.
CNC-Calc requires an extended license for CIMCO Edit Professional.
Disable Mazatrol Viewer
Select this option to disable the Mazatrol Viewer module.
Mazatrol Viewer requires an extended license for CIMCO Edit.
Configuration Password
Enable configuration password protection
...
Set password
Click this button to specify a password required for accessing the Editor Setup and its configuration.
If you forget the password, hold down
Ctrl+Shift
when you start the editor.
Edit configuration paths
Use this option to change the location and directories that CIMCO Edit uses for various configuration files.
Use the dropdown field to select a path and the field below to change it.
You can choose to copy the existing configuration files to the new directory or revert to the default configuration if needed.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/installation/
TITLE: Installation
======================================================================
PDF
Installation
Installation
To install CIMCO Edit 2026, follow the instructions below.
Before you install or use any CIMCO product, we recommend that you verify that your computer meets or exceeds the
minimum system requirements
.
Locate Installation Files
If you receive CIMCO Edit 2026 via a download link, memory stick, or external drive, copy the installation file to a temporary directory on the PC/Server before proceeding.
Run Installation Program
First you must log on using an account with full administrative privileges.
Start the installation program by clicking on the setup application (
CIMCOEdit_2026xxxx.exe). Now follow the instructions of the Setup Wizard that will guide you through the installation steps.
When the installation is completed, you will find a shortcut to the CIMCO Edit 2026 application in the CIMCO 2026 program group in the
Start
menu and in the desktop.
CIMCO Edit 2026 icon.
Notes on additional install options
The option
Place configuration in install directory
will place the user files (configuration, macros, tool libraries...) in the installation directory. This will allow all the users on the PC to run CIMCO Edit with the same settings.
If this option is not checked, the user files (configuration, macros, tool libraries...) will be placed in the application specific data folder for the user profile (C:\Users\"
username
"\AppData\Roaming), so every user in the computer will run CIMCO Edit with its own user files.
More information related to this option can be found in Plugins.
Installing your License File
If you do not have a license file but wish to install an evaluation version, just proceed to the next step.
If you have received a license file from CIMCO, it should be installed by double-clicking on the file "
CustomerName-license.CimcoLicense
" after the installation is completed. This opens the CIMCO License File Viewer. Click on the button
Install license file
to install the license file. If the license file requires activation, the program will display the options for doing this. See
CIMCO Software Activation
for further information.
Starting the Editor
When the installation is completed and you have installed your license file, you are ready to start the editor for the first time. Click on the program icon on your desktop.
CIMCO Edit 2026.
After starting the editor, please verify that your company name is shown in the
Licensed to
field in the
About
box. If not, the license file was not installed correctly. Please repeat the point 'Installing your License File' above in order to install the license file correctly.
If you are running an evaluation version, the license name is
Demo version
.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/installation/software-activation/
TITLE: CIMCO Software Activation
======================================================================
PDF
Installation
CIMCO Software Activation
CIMCO Software Activation
To ensure that the License File is not copied and used elsewhere, the License File can be locked to a specific computer using an activation process. Once the system is activated, the License File cannot be used on another system unless the activation is reset.
The software activation process is not needed for temporary license files.
Online Activation
After selecting the license file that CIMCO Edit will use, if the license file requires activation, the program will display the following message:
Software activation dialog.
If the computer running CIMCO Edit has access to the Internet, just click the
Yes
button and the activation process will be done automatically.
Software activation completed successfully.
Offline Activation
If the computer running CIMCO Edit is not connected to the Internet, then the following dialog will be displayed:
Software activation dialog.
Click on the button
Create Activation Request
. This will generate an activation request file (.request) that contains information from the computer in order to uniquely identify the system. Give to this file any filename, select where you want to save this file and click
Save
.
The activation can only be done contacting the CIMCO's activation server, so copy the generated .request file to a portable device and proceed to a computer with Internet connection.
Open a web browser and go to the Activation page on the CIMCO web site at
www.cimco.com/support/activate-software
Software Activation web page.
Click in the
Choose File
button and navigate to the activation request file (.request). Once the file is selected, click the
Upload File
button.
Upload Activation File.
The server will verify the activation request and will generate an Activation File. If any error occurs during the activation, it will be displayed in the Activation box. If the activation is successful, a link to download the Activation File will be shown.
Download Activation File.
Save the generated Activation File (.activation) and go back to the computer running CIMCO Edit which we want to activate. In the software activation dialog, click now in the
Use activated request
button. Select the Activation File (.activation) and click
Open
. The software should be now activated and ready to use.
Use activated request file downloaded from the CIMCO web site.
After the activation is completed, you can see information about the activation in the License File Viewer.
Activation information.
The License File can also be activated directly from the License File Viewer. Once the button
Activate license file
is pressed, the process is the same as described for Online Activation or Offline Activation depending if the computer is connected to the Internet or not.
License activation from the License File Viewer dialog.
Re-activation
If the computer running CIMCO Edit needs to be replaced, a new software activation is needed, and the activation needs to be reset before going through the activation process in the new system or the following error will be displayed. Please contact your reseller or CIMCO Support in order to get your activation reset.
License File already activated.
If the OS needs to be re-installed or upgraded, a new software activation may be required. But since the computer hardware is unchanged (same CPU, hard drive, MAC address...) it should not be necessary to contact your reseller or CIMCO Support to reset the activation.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/introduction/
TITLE: CIMCO Edit 2026 User Guide
======================================================================
PDF
Introduction
CIMCO Edit 2026 User Guide
CIMCO Edit is the world's most popular CNC program editor. It is a reliable, full-featured editing, simulation and communication tool that allows you to work with NC programs on your PC, in a familiar Windows-based application. CIMCO Edit comes with all the essential features needed for modern NC program editing, including NC specific functions, math, transforms, drag/drop editing and more. In addition, CIMCO Edit includes file compare, mill/turn simulation, Tool Manager, NC code assistant and offers powerful add-ons for machine simulation, program management, 2D CAD/CAM, and more.
This user guide will help you get started with CIMCO Edit and learn how to use its various features and functions. You will also find information on how to customize and configure CIMCO Edit to suit your needs and preferences. Whether you are a beginner or an expert CNC programmer, CIMCO Edit will help you write error-free NC code and identify problematic toolpaths and tool motion.
We hope you enjoy using CIMCO Edit.
Table of Contents
Introduction
System Requirements
Installation
Program Tabs
Simulation
DNC Setup
Editor Setup
Regular Expressions
Using Editor Help
Pending Updates
Subsections
License Information
Contact Information
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/introduction/contact/
TITLE: Contact Information
======================================================================
PDF
Introduction
Contact Information
Contact Information
CIMCO A/S
Vermundsgade 38A, 3
2100 Copenhagen Ø
Denmark
Tel: +45 4585 6050
Fax: +45 4585 6053
E-mail:
info@cimco.com
Web:
www.cimco.com
CIMCO Americas, LLC
1980 N Atlantic Ave Ste 229
Cocoa Beach, FL 32931
USA
Tel: +1 704 644 3587
Fax: +1 704 943 0514
E-mail:
info@cimcous.com
Web:
www.cimco.com
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/introduction/license/
TITLE: End User License Agreement
======================================================================
PDF
Introduction
License Information
End User License Agreement
END USER LICENSE AGREEMENT
CONCERNING
CIMCO Software 2026 (the “Software”)
WARNING! IF YOU COMPLETE THE INSTALLATION OF THIS SOFTWARE OR IF YOU ACTIVATE THE SOFTWARE, YOU ARE CONSIDERED TO HAVE ACCEPTED – AND YOU WILL BE LEGALLY BOUND BY - THIS END USER LICENSE AGREEMENT.
1. SCOPE:
This End User License Agreement (the "License Agreement") sets out the terms and conditions of your license to install, access and use the standard version of the Software specified above, including upgrades and accompanying documentation. This License Agreement covers the Software in the unmodified standard version and all subsequent upgrades thereof, which is made available to you by or on behalf of CIMCO A/S, corporate ID CVR32323510, Vermundsgade 38, 3. floor, 2100 Copenhagen, Denmark (the "Licensor").
2. GRANT OF LICENSE AND EFFECTIVE DATE:
Conditional upon your payment of the agreed license fee, Licensor grants you a non-exclusive, non-transferable and perpetual license (a "License") to install, access and use the Software, but only in object-code format, on the terms and conditions set forth herein. The number of Licenses you have acquired and paid for, determines the number of copies of the Software you are permitted to make and the number of end users which may access and use the Software. One (1) License covers one (1) copy of the Software and permits one (1) end user to access and use the Software. The effective date of your License(s) is the date, where you for the first time have paid the applicable license fee.
3. TITLE AND PROPRIETARY INFORMATION:
Full title to the Software shall remain with Licensor and nothing in this License Agreement shall be construed as a transfer of Licensor’s title to the Software to you or to any third party. If you install the Software you automatically acknowledge and accept that the Software represents valuable trade secrets to Licensor, and that you must keep and use the Software in confidence and in accordance with the terms and conditions of this License Agreement.
4. REPRODUCTION OF SOURCE CODE:
You agree not to disassemble, reverse compile, or reverse engineer the Software or any part thereof, or take any other action in order to reproduce the source code of the Software, except as expressly permitted in article 6 of Directive 2009/24/EC of the European Parliament and of the Council of 23 April 2009 on the legal protection of computer programs as incorporated into Danish law by article 37 of the Danish Act No. 1144 of October 23, 2014 on Copyrights (in Danish “Ophavsretsloven”). Therefore, the License includes a limited right for you as the Licensee to reproduce the source code of the Software on the following conditions, which shall all be fulfilled at the relevant time: (a) reproduction of the source code is indispensable to obtain the information, which is necessary to achieve interoperability between the Software and other programs, (b) the task of reproduction of the source code is performed by you or by another person having a right to use the Software, or on your behalf by a person authorized to do so; (c) the information necessary to achieve interoperability have not previously been readily available to you; and (d) reproduction of source code is confined to those parts of the Software which are necessary in order to achieve interoperability. You shall not under any circumstances (e) use information obtained through reproduction of the source code of the Software for any other purpose than to achieve the interoperability of the Software; (f) give such information to others, except when necessary to achieve the desired interoperability of the Software; or (c) use such information for the development, production, or marketing of a software program substantially similar to the Software in its expression, or for any other acts which infringe Licensor’s copyright.
5. COPYING THE SOFTWARE:
You agree not to copy the Software, except as expressly permitted in the articles 4 and 5 of Directive 2009/24/EC of the European Parliament and of the Council of 23 April 2009 on the legal protection of computer programs as incorporated into Danish law by article 36 of the Danish Act No. 1144 of October 23, 2014 on Copyrights ( in Danish “Ophavsretsloven”). Therefore, the License includes a limited right for you as the Licensee (a) to make such number of internal copies of the Software, which are strictly necessary to ensure the Software performs in accordance with its objectives; and (b) to make an internal back-up copy of the Software, if, and to the extent, this is necessary for your use of the Software.
6. TERMINATION AND EFFECTS OF TERMINATION:
You may terminate this License Agreement upon thirty (30) days written notice to Licensor. Licensor may immediately terminate any or all Licenses without further obligation or liability (a) if you fail to pay the applicable license fee or any other amount due hereunder and you continue to be delinquent for a period of thirty (30) days after the last day on which payment was due; or (b) if a petition alleging insolvency is filed by or against you, or a receiver is appointed for any part of your business, or your assets are assigned for the benefit of your creditors; or (e) if you commit any other breach of this License Agreement and fail to remedy such breach within thirty (30) days after written notice by Licensor of such breach, or (d) if you violate anyone of the Articles 3, 4, or 5 herein. Upon termination of this License Agreement or any License granted hereunder, you shall immediately cease using the Software and without delay un-install and destroy all copies of the Software and all related documentation. Termination of this License Agreement or any License granted hereunder shall not release you from the obligations of the Articles 3, 4 and 5 herein. The termination of this License Agreement shall not affect the survival of the representations, warranties, and covenants contained herein.
7. INDEMNIFICATION OF LICENSOR:
You agree to indemnify and hold harmless Licensor, its distributors and its retailers and each of their respective officers, directors, and employees against any and all losses, liabilities, expenses (including reasonable attorneys' fees) suffered or incurred by them by reason of any claim, suit or proceedings arising out of or in connection with: (a) any content, information, or other materials posted, provided, uploaded, submitted, shared, published, distributed, made available, accessible or usable on, to, from or through the Software ("User Content"); or (b) any illegal or damaging usage of User Content, such as, but not limited to, usage infringing upon intellectual property rights or violating trade secrets or other rights, or causing death or bodily injury or damage to tangible assets or real property; or (c) any breach of or failure by you to comply with this License Agreement; or (d) any other use of the Software made by you (or by anyone who accesses the Software through you).
8. DISCLAIMER OF ALL WARRANTIES:
EXCEPT FOR THE EXPRESS LIMITED WARRANTY PROVIDED IN THIS LICENSE AGREEMENT, IF ANY, AND TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, LICENSOR MAKES, AND YOU (IN YOUR CAPACITY OF LICENSEE) RECEIVE, NO WARRANTIES, REPRESENTATIONS, OR CONDITIONS OF ANY KIND, EXPRESS OR IMPLIED (INCLUDING, WITHOUT LIMITATION, ANY IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT, OR WARRANTIES OTHERWISE IMPLIED BY STATUTE OR FROM A COURSE OF DEALING OR USAGE OF TRADE) WITH RESPECT TO THE LICENSED SOFTWARE. ANY STATEMENTS OR REPRESENTATIONS ABOUT THE LICENSED SOFTWARE AND ITS FEATURES OR FUNCTIONALITY IN ANY MATERIALS PROVIDED TO OR IN ANY COMMUNICATION WITH YOU ARE FOR INFORMATION PURPOSES ONLY, AND DO NOT CONSTITUTE A WARRANTY, REPRESENTATION, OR CONDITION. WITHOUT LIMITING THE FOREGOING, LICENSOR DOES NOT WARRANT THAT THE OPERATION OR OUTPUT OF THE LICENSED SOFTWARE WILL BE UNINTERRUPTED, ERROR-FREE, SECURE, ACCURATE, RELIABLE, OR COMPLETE, WHETHER OR NOT UNDER SUPPORT BY LICENSOR OR ANY THIRD PARTY. NOTHING IN THE FOREGONG SHALL RESTRICT THE EFFECT OF WARRANTIES OR CONDITIONS WHICH MAY BE IMPLIED BY LAW AND WHICH CANNOT BE EXCLUDED, RESTRICTED OR MODIFIED NOTWITHSTANDING A CONTRACTUAL RESTRICTION TO THE CONTRARY.
9. LIMITATION OF LICENSOR’S LIABILITY:
IN NO EVENT WILL LICENSOR HAVE ANY LIABILITY ( DIRECTLY OR INDIRECTLY) FOR ANY INCIDENTAL, SPECIAL, INDIRECT, CONSEQUENTIAL, OR PUNITIVE DAMAGES, FOR LOSS OF PROFITS, USE, REVENUE, DATA, OR FOR BUSINESS INTERRUPTIONS. IN ADDITION, THE MAXIMUM LIABILITY OF LICENSOR ARISING OUT OF OR RELATING TO THE LICENSED SOFTWARE WILL NOT EXCEED AN AMOUNT CORRECPONDING TO THE AGGREGATE LICENSE FEES PAID OR PAYABLE BY LICENSEE FOR THE LICENSES COVERED BY THE LICENSE AGREEMENT. THE LIMITATIONS OF LIABILITY IN THIS ARTICLE 9 WILL APPLY TO THE EXTENT PERMITTED BY APPLICABLE LAW TO ANY DAMAGES OR OTHER LIABILITY, HOWEVER CAUSED AND REGARDLESS OF THE THEORY OF LIABILITY, WHETHER DERIVED FROM CONTRACT, TORT (INCLUDING, WITHOUT LIMITATION, NEGLIGENCE), OR OTHERWISE, EVEN IF LICENSOR HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH LIABILITY AND REGARDLESS OF WHETHER THE LIMITED REMEDIES AVAILABLE HEREUNDER FAIL OF THEIR ESSENTIAL PURPOSE. ALSO, YOU ACKNOWLEDGE AND AGREE THAT THE LICENSE FEES PAID BY YOU ARE BASED ON AND REFLECTIVE OF THE ALLOCATION OF RISK CONTEMPLATED BY THIS ARTICLE 9 AND THAT THE LIABILITY LIMITATIONS HEREIN ARE AN ESSENTIAL ELEMENT OF THIS LICENSE AGREEMENT.
10. SALE OF LICENSES TO THE UNITED STATES GOVERNMENT:
For U.S. Government procurements, the Software is deemed to be commercial computer software as defined in FAR 12.212 and subject to restricted rights as defined in FAR Section 52.227-19 "Commercial Computer Software - Restricted Rights" and DFARS 227.7202, "Rights in Commercial Computer Software or Commercial Computer Software Documentation", as applicable, and any successor regulations. Any use, modification, reproduction release, performance, display or disclosure of the Software by the U.S. Government will be solely in accordance with license rights and restrictions described therein.
11. SEVERABILITY:
Should any provision of this License Agreement be invalid, ineffective, or unenforceable, under present or future laws, the remainder of the provision shall remain in full force and effect and shall in no way be affected, impaired or invalidated.
12. ENTIRE AGREEMENT:
You acknowledge that you have read this License Agreement before you complete installation of the Software or before you access and start using the Software and you acknowledge and agree that this License Agreement is the complete and exclusive statement of the agreement between us, and that it supersedes all prior proposals and understandings, oral and written, relating to the Software licensed pursuant to this License Agreement. This License Agreement shall not be modified or rescinded except in writing signed by both of us. Notwithstanding the aforementioned sentences, you acknowledge and accept that the licensed Software may contain or be accompanied by third-party software, data, or other materials that are subject to and provided in accordance with third-party license terms that are in addition to or different from the terms set forth in this License Agreement. Such third-party license terms may be included or referenced to or with such third- party software, data, or other materials (e.g., in the "About box"), or at a web page specified by Licensor (the URL for which may be obtained on request to Licensee). You hereby agree to comply with such third-party terms as the case may be.
13. CHOICE OF LAW AND VENUE:
You acknowledge and accept that this License Agreement and all aspects of the agreement, including the construction, interpretation, and validity of the agreement, shall be exclusively governed by Danish law, except its conflict of laws rules. Any dispute between us related to this License Agreement and which cannot be otherwise settled by our agreement, must be brought before the courts of Denmark to the exclusion of the courts of any other jurisdiction.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/pending-updates/
TITLE: Pending Updates to Documentation
======================================================================
PDF
Pending Updates
Pending Updates to Documentation
The following changes to CIMCO Edit 2026 are currently not described in the documentation.
CIMCO Edit 2026.01.23
New: Added 'Insert Side' to Tool Mount Properties.
New: Collinear axes in the work offsets table.
New: Showing programmed work offsets. (S30073)
CIMCO Edit 2026.01.22
New: Clickable view cube.
New: Grid-lines in Backplot.
New: Now shows license info in presentation viewer status bar.
CIMCO Edit 2026.01.20
New: Machines are now grouped in Machine Builder by 'My machines' and 'Preconfigured machines'.
CIMCO Edit 2026.01.17
New: Added Off Center Turret generic lathe and 45 degree table/head machine.
New: Backplot active selection with live updates as you change the selection.
New: Tool path statistics: min/max spindle speed.
New: Tool list: extraction from tool call line.
New: Custom turret slot orientations now supported.
CIMCO Edit 2026.01.12
New: Added optional synchronization command mapping for matching different command numbers, such as M770 and M775, in multi-channel synchronization.
Change: "Ignore block skip" is moved from control settings to simulation settings.
New: Tool manager: added tool station number to "Advanced tool location" in turning/mill-turn mode. (S29248)
CIMCO Edit 2026.01.07
New: New real-time based simulation animation speed slider.
New: Added gage point to custom lathe holders.
CIMCO Edit 2026.01.03
New: Added Clamp/unclamp time settings.
New: Advanced Chuck Jaw setup.
New: Statistics can show graph for selected tools. (S27148)
New: Default view can now be changed in the machine configuration editor.
New: Now bundles external sub programs in simulation bundles.
New: Support vertical milling extenders.
CIMCO Edit 2026.01.01
New: Command line (--savebundle path) for saving simulation bundle.
CIMCO Edit 2025.01.30
New: Added 'Remove chips' simulation setting.
New: Gradient toggle in stock compare.
CIMCO Edit 2025.01.28
New: Showing currently called subprogram's code in fast simulation. (S23299)
New: Added color picker to tool assemblies.
New: Toolpath color by tool now supported in the fast simulation window.
CIMCO Edit 2025.01.22
New: Redesigned the Bookmarks dialog with a cleaner multi-column layout, built-in filtering, and easier navigation.
New: Redesigned the Find All Search Results dialog with a cleaner multi-column layout, built-in filtering, and - easier navigation.
New: Added show/hide workpiece to the ribbon bar.
New: Added show/hide fixture to the ribbon bar.
New: Can now toggle stock visibility in the ribbon bar.
Change: Moved toolpath bounding box and toolpath origin dropdown items to the toolpath ribbon bar split button.
CIMCO Edit 2025.01.21
New: Added goto next/prev navigation when in animation navigation mode.
CIMCO Edit 2025.01.20
New: Added Cutter Point Shift to Parting and Grooving tools.
New: Select and delete multiple geometries as once in the machine builder.
New: Turret tool mount STL and tool location can now be changed in the tool manager.
New: Added generic machine with angle head.
New: Angle heads can now be added to tool assemblies.
CIMCO Edit 2025.01.19
New: Added show active plane and show current navigation to animation mode.
New: Now shows tool name in simulation.
CIMCO Edit 2025.01.15
New: Collision detection option added for static head models in the machine builder.
CIMCO Edit 2025.01.13
New: Added 'jump to cut' feature.
New: Added 'color toolpath by feedrate' feature.
CIMCO Edit 2025.01.12
New: Sub-Spindle Offset setting.
CIMCO Edit 2025.01.11
New: Stock transfer and dual spindle machine simulation support.
New: Added --no-bring-to-front flag to prevent the editor from being brought to the foreground when called via command line. (S25874)
New: Now shows the machine origin in machine builder.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/regex/
TITLE: Regular Expressions
======================================================================
PDF
Regular Expressions
Regular Expressions
The regex used in CIMCO Edit is based on POSIX Extended Regular Expression, with some simplifications.
You can read more about POSIX Extended Regular Expression (ERE) online:
https://en.wikipedia.org/wiki/Regular_expression
https://en.wikibooks.org/wiki/Regular_Expressions/POSIX-Extended_Regular_Expressions
Syntax
Metacharacter
Description
.
Dot character matches any character.
For example, "A.C" Matches "A" followed by any character and then a "C". To match the literal "." character use a backward slash \. or bracket expression [.].
^
Matches the starting position of the line.
For example, "G123" matches the character sequence "G123" anywhere on the line, "^G123" only matches "G123" if located at beginning of the line. To match the literal "^" character use a backward slash "\^" outside of bracket expressions.
$
Matches the ending position of the line.
For example, "G123" matches the character sequence "G123" anywhere on the line, "$G123" only matches "G123" if located at the end of the line. To match the literal "$" character use a backward slash "\$" outside of bracket expressions.
[ ]
Bracket expression. Matches any of the characters within the brackets.
For example, "[AZ]" matches one of the characters "A" or "Z". A range can be specified by using "-". E.g. "[A-Z]" matches any character in the range from "A" to "Z" and "[4-7]" matches any number from "4" to "7". To match the literal "[" or "]" character use a backward slash [ or ] outside of bracket expressions.
[^]
Matches any character not within the brackets.
For example, "[AZ]" matches any character other than "A" or "Z". A range can be specified by using "-". E.g. "[A-Z]" matches any character other than the letters from "A" to "Z" and "[4-7]" matches any other than the numbers from "4" to "7".
*
Matches the preceding element zero or more times.
For example, "G[0-9]*" matches "G" followed by zero or more numbers between "0" and "9". To match the literal "*" character use a backward slash "\*" or bracket expression "[*]".
+
Matches the preceding element one or more times.
For example, "G[0-9]+" matches "G" followed at least one number between "0" and "9". To match the literal "*" character use a backward slash "\+" or bracket expression [+].
?
Matches the preceding element one or zero times.
For example, "AB?C" matches the sequence "ABC" or "AC". To match the literal "?" character use a backward slash "\?" or bracket expression [?].
|
Matches the preceding or the following element.
For example, "AB|C" matches "AB" or "AC". To match the literal "|" character use a backward slash "\|" or bracket expression [|].
{n}
Matches the preceding element exactly n times.
For example, "A{3}" matches "AAA".
{n,}
Matches the preceding element minimum n times.
For example, "A{3,}" matches any character sequence with at least three "A"s.
{,m}
Matches the preceding element maximum n times.
For example, "A{,3}" matches any character sequence with at maximum three "A"s.
{m,n}
Matches the preceding element at least n and not more than m times.
For example, "A{2,4}" matches any character sequence with at minimum two and maximum four "A"s.
()
Grouping. Matches the group of characters within the brackets.
For example, "(G[1-3])|(M[4-7])" matches "G" followed by a number between 1 and 4 or matches "M" followed by a number between 4 and 7.
<>
Capture. Matches the subexpression within the brackets.
For example. "G<[0-9]+>" matches one or more numbers following "G", excluding "G" from the match.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/system-requirements/
TITLE: General System Requirements
======================================================================
PDF
System Requirements
General System Requirements
The following are the general system requirements for CIMCO software products. These requirements cover different types of installations, including servers, clients, and simulation components. Some sections may therefore not apply to the product or features described in this guide.
Hardware requirements may vary depending on the product, installed components, system configuration, and operating system.
Server Installation
Component
Minimum
Recommended
Processor
4 logical processors
8-12 logical processors
Memory
4 GB RAM
16 GB RAM
Storage
512 GB HDD
512 GB SSD
Disk space
2 GB free space for installation
Additional space for database growth
Operating system
Windows Server 2016, 64-bit
Windows Server 2016 or newer, 64-bit
For production server installations, use reliable storage with appropriate backup and redundancy.
Additional Software
The following components are required and are included in the installer:
Microsoft Visual C++ v14 Redistributable, for Visual Studio 2017-2026
Microsoft .NET Framework 4.8
Server Sizing by Number of CNC Machines
CNC machines
Logical processors
20
4
100
8
200
12
325
16
1000
32
External Database Support
Database
Minimum version
Microsoft SQL Server
SQL Server 2016 or newer
Client Installation
Component
Minimum
Recommended
Processor
Dual-core processor
Quad-core processor or better
Memory
2 GB RAM
4 GB RAM
Disk space
2 GB free space
2 GB free space
Operating system
Windows 10, 64-bit
Windows 10 or newer, 64-bit
Additional Software
The following components are required and are included in the installer:
Microsoft Visual C++ v14 Redistributable, for Visual Studio 2017-2026
Microsoft .NET Framework 4.8
Display, Network and Input
Component
Requirements
Display
OpenGL 3.3 compatible graphics card for Backplot and Solid Animation. Minimum screen resolution of 1024 × 768 pixels.
Network
Network adapter with TCP/IP enabled when using network licensing or client/server solutions.
Input
Standard keyboard and mouse.
Licensing
A valid CIMCO license file is required for licensed operation.
Simulation Requirements
These requirements apply to the faster simulation introduced in CIMCO Edit 2022.01.11.
Component
Minimum
Recommended
Processor
Dual-core processor
Octa-core processor or better
Graphics
Dedicated GPU with 2 GB memory and OpenGL 4.3
Dedicated GPU with 4 GB memory and OpenGL 4.3 or better, such as NVIDIA RTX 2060 or better
Memory
8 GB RAM
16 GB RAM or more
Operating system
Windows 10, 64-bit
Windows 10 or newer, 64-bit
Machine Simulation Requirements
The following requirements apply to the CIMCO Machine Simulation add-on.
Component
Minimum
Recommended
Processor
Quad-core processor, 2.3 GHz
Quad-core processor, 3.2 GHz or better
Graphics
Dedicated GPU with 2 GB memory and OpenGL 3.3
Dedicated GPU with 4 GB memory and OpenGL 3.3 or better
Memory
4 GB RAM
16 GB RAM or more
Operating system
Windows 10, 64-bit
Windows 10 or newer, 64-bit
License Server
The License Server has these requirements:
Type
Requirement
Operating system
64-bit Windows (the installation program is for 64-bit Windows only)
Software
Microsoft® .NET Framework 4.8 (included within the installer)
Microsoft® Visual C++ Redistributables (included within the installer)
A license file that contains a license for the License Server
User rights
Administrative privileges to install the software, and to start and stop the License Server service
Network
Network adapter with TCP/IP enabled
The License Server listens on TCP port 4460 by default (see
Settings
) and answers searches from clients on UDP port 4451. Both must be allowed through any firewall between the clients and the License Server
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.