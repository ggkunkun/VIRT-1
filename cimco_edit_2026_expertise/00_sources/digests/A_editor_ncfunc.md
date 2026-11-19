# 官方语料摘录 A_editor_ncfunc（共 26 页，源自 docs.cimco.com/en/docs/edit/2026/）


======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/
TITLE: Program Tabs
======================================================================
PDF
Program Tabs
Program Tabs
The functions in CIMCO Edit 2026 are activated using the appropriate icons on the Ribbon bar. The options are organized into logical groups under tabs.
If the function can be activated through the Ribbon bar or a keyboard shortcut, the icon or the shortcut is displayed next to the command name.
Subsections
Editor
NC Functions
NC-Assistant
Backplot
File Compare
Transmission
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/
TITLE: Editor
======================================================================
PDF
Program Tabs
Editor
Editor
This section describes the options in the
Editor
tab.
Subsections
File
File Type
Edit
Find
Bookmarks
Setup
Window
Help
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/bookmarks/
TITLE: Bookmarks
======================================================================
PDF
Program Tabs
Editor
Bookmarks
Bookmarks
This section describes the options in the
Bookmarks
menu. These allow you to bookmark lines and locations in a document.
Bookmarks menu.
Bookmark indicators are shown by highlighting the line number. Make sure the
Show line numbers
option is enabled in the
Editor Settings
to see the bookmarks.
Menu options
View Bookmarks
Click this option to open the
Bookmarks
dialog, which lists the bookmarks in all open documents. The list shows the file, line number, bookmark name and path of each bookmark.
Filter bookmarks:
Type in this field to show only matching bookmarks. You can type several words separated by spaces. A bookmark is shown when every word matches its file name, line number, name or the text on the line.
Go to:
Goes to the selected bookmark. You can also double-click a bookmark.
< Previous / Next >:
Goes to the previous or next bookmark in the list (Shift+F5 / F5).
Delete Bookmark:
Deletes the selected bookmark.
Clear all Bookmarks:
Deletes all bookmarks after you confirm.
Close:
Closes the dialog.
Bookmarks will only show up in this dialog if the document has been saved.
Bookmarks dialog.
Go to Previous /
Shift+F5
Jumps to the previous bookmark found in the document.
Go to Next /
F5
Jumps to the next bookmark found in the document.
Add Bookmark (Remove Bookmark) /
F2
Click this option to create a bookmark on the selected line. Use the Add Bookmark dialog to give a name to the bookmark.
Add Bookmark dialog.
If there is already a bookmark on the selected line, this option will display
Remove Bookmark
instead. Click this to remove the bookmark.
Toggle Indicators
Toggles display of bookmark indicators.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/edit/
TITLE: Edit
======================================================================
PDF
Program Tabs
Editor
Edit
Edit
This section describes the options in the
Edit
menu. These are mostly standard options for editing text plus options for appending text from external files.
Edit menu.
To select a specific segment of text, click and hold the left mouse button at the desired starting point, then drag the cursor to the end point. The selection will be visually represented by a change in background color, signifying the selected area. For details on color indications, refer to the
Global Colors
.
Menu options
Copy /
Ctrl+C
Copies the selected text to the clipboard.
Cut /
Ctrl+X
Deletes the selected text and saves it on the clipboard.
To paste the cut-out selection at another location in the file, place the cursor there and choose the command
Paste
.
Paste /
Ctrl+V
Inserts the clipboard contents, after
Copy
or
Cut
, at the current cursor position.
Select All /
Ctrl+A
Selects all lines in the file.
Undo /
Ctrl+Z
Undo the last operation.
Redo /
Ctrl+Y
Redo the last
Undo
operation. You can
Redo
all
Undo
operation since the file was last opened.
Mark/Delete range /
Ctrl+M
When selecting
Mark/Delete range
, the following dialog appears:
Mark/Delete dialog.
This dialog allows you to specify a range of lines or block numbers to be updated, selected or deleted. It is possible to make a special selection (or deletion) from a tool change, feed rate or spindle speed value up till the next.
You can also access this dialog from the
Insert/Remove
menu under the NC Functions tab.
Append File
Appends a file to the end of the current CNC program.
Insert File
Inserts a file into the current window at the cursor position.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/file/
TITLE: File
======================================================================
PDF
Program Tabs
Editor
File
File
This section describes the options in the
File
menu.
File menu.
Menu options
New /
Ctrl+N
Select this option to create an empty program/file, ready for input.
Open /
Ctrl+O
Select this option to open a file.
Advanced Open /
Ctrl+Alt+O
The
Advanced Open
file dialog lets you to locate files by specifying search criteria on file name, file content, and created/modified dates. Click the down arrow of the
Open
icon to access this option.
Advanced Open File dialog.
Recent
A list of recently used files. Click the down arrow of the Open icon to open recently used files.
Recent list.
Close /
Ctrl+F4
Closes the current window. You will be prompted to save changes if the file has been modified.
Close All
Closes all open windows. You will be prompted to save changes for all modified files. Click the down arrow of the Close icon to access this option.
Save /
Ctrl+S
Saves the current CNC program.
Save All
Saves all open CNC programs under their current names. Click the down arrow of the Save icon to access this function.
Save As
Saves the current CNC program under a new name.
Save as associated file
Saves the current CNC program in CIMCO NC-Base. When selected, the user will be prompted to select
Machine
,
Program Name
and enter a
filename
. The program will then be saved and associated with the selected program in CIMCO NC-Base.
Print /
Ctrl+P
Prints the current CNC program. If you want to print a part of a program, mark the area of interest and choose
Print
.
Printer Setup
The dialog window for printout configuration is opened. Click the down arrow of the Print icon to open this option. Please refer to section Printing for more details.
Global setup
This option lets you configure the general program settings of CIMCO Edit, also accessible through the icon
. Please refer to section Editor Settings for more details.
Most of the
File
functions described above can also be reached through the general
File
menu.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/filetype/
TITLE: File Type
======================================================================
PDF
Program Tabs
Editor
File Type
File Type
This section describes the options in the
File Type
menu.
The
File Type
options determine how renumbering is performed, how tool changes are identified, Backplot settings, colors, where files are saved, etc.
File Type menu.
Menu options
File Type
Use this dropdown list to select a file type. The file type determines the coloring, syntax, etc.
Colors
Opens the
Color Settings
in the
Editor Setup
for the selected file type. Use this to define the color highlighting for the file type.
Configure Block Numbering
Opens the
Block Numbers
dialog in the
Editor Setup
for the selected file type. Use this to configure block numbering.
Directories / Extensions
Opens the
Load/Save
dialog in the
Editor Setup
for the selected file type. Use this to configure directories and extensions.
Machine Templates
Opens the
Machine
dialog in the
Editor Setup
for the selected file type. Use this to configure machine template specific parameters.
Other Settings
Opens the
Other
dialog in the
Editor Setup
for the selected file type. Use this to configure additional machine settings.
Configure Machine Type
Opens the
File Types
dialog in the
Editor Setup
. Use this dialog to add new or configure existing file types.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/find/
TITLE: Find
======================================================================
PDF
Program Tabs
Editor
Find
Find
This section describes the options in the
Find
menu. These options are used for searching or jumping to a location in the current file.
Find menu.
Menu options
Find /
Ctrl+F
Click this option to open the
Find
dialog.
Search dialog.
Find what:
Enter the text to search for in the
Find what
field. If a text selection was made before clicking the
Find
option, this will be auto-inserted in the
Find what
field.
Match whole string:
Select this option to only match the exact string in the
Find what
field.
Ignore case:
Select this option to ignore if letters are uppercase or lowercase.
Use regular expression:
Select this option to interpret the text in the
Find what
field as a Regular Expression such as \(\((.*?)\)\) - to find the text between (( and )). See
Regular Expressions
for more information.
Search all:
Select this option to search through all open files.
Find NC Command:
Use this dropdown to search for a Tool Change, Feedrate or Spindle Speed. How these are identified is configured in the
Editor Setup
under the
File Types
dialog.
Next/Previous:
Use these buttons to go to the next or previous search result.
Bookmark All:
Click this button to create
Bookmarks
from all search results.
Find All:
Click this button to list all matching search results in the
Search results
dialog. The title shows the number of hits and files. The list shows the file, line number, text and path of each result. Type in the
Filter search results
field (F6) to show only the results where every word matches the text, path or line number. Use
Go to
or double-click a result to go to it. Use
< Previous
and
Next >
(Shift+F8 / F8) to step through the results. Press Ctrl+F to open the
Find
dialog again.
Find Previous /
Shift+F3
Finds the previous occurrence of the specified search string in the file.
Find Next /
F3
Finds the next occurrence of the specified search string in the file.
Replace /
Ctrl+H
Click this option to replace a specified string in the file with another string.
Replace dialog with option
Multiline
enabled.
Find what:
Enter the text string that should be replaced. If
Multiline
is enabled, more lines of text can be entered.
Replace with:
Enter the text string to replace with. If
Multiline
is enabled, more lines of text can be entered.
Ignore case:
Select this option to ignore if letters are uppercase or lowercase.
Replace in selection only:
Select this option to only perform the replace operation on the selected lines.
Match whole string:
Select this option to only match the exact string in the
Find what
field.
Result to new window:
Select this option to create a new, duplicate document with the replaced text.
Use regular expression:
Select this option to interpret the text in the
Find what
field as a Regular Expression.
Multiline:
Select this option allow multiple lines in the
Find what
and
Replace with
fields.
Replace All from File:
Select this option to import one or more replace statements from an external file. Each line in the external file should define a find/replace pair. Once selected, a field will appear to enter the
Delimiter
used in the external file (such as a semi-colon for the pair T1;T10). Finally, click the
Replace All
button, select the file with the find/replace statements and press OK.
Dialog to select the replace list.
Go to Line/Block Number /
Ctrl+J
Move curser to line or block number in the current file.
Next Tool Change
Move curser to next tool change.
Previous Tool Change
Move curser to previous tool change.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/help/
TITLE: Help
======================================================================
PDF
Program Tabs
Editor
Help
Help
If you need help with CIMCO Edit, click on the
Help
dropdown in the upper right corner of the Ribbon. Help in CIMCO Edit is further explained in
Using Editor Help
.
Help menu.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/setup/
TITLE: Setup
======================================================================
PDF
Program Tabs
Editor
Setup
Setup
Setup
Click this to enter the
Editor Setup
dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/editor/window/
TITLE: Window
======================================================================
PDF
Program Tabs
Editor
Window
Window
This section describes how the open documents in CIMCO Edit can be visually arranged.
Click on the small
Window
dropdown at the top right corner of the Ribbon. This will open a menu with four display modes and a list of open documents.
Click on a mode to change the layout of open documents or click on a document in the list to make this the active document.
Window menu.
Menu options
Dark Theme
Select this to enable dark theme. The dark theme reduces the luminance emitted by device screens by emitting low levels of light while maintaining a high standard of usability.
Cascade
Places the open files in an overlapping cascade.
Arrange icons
Assembles the icons of the minimized documents in the lower left corner of the editor window.
Tile Horizontally
Places the open documents horizontally one after the other.
Tile Vertically
Places the open documents vertically one after the other.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/
TITLE: NC-Assistant
======================================================================
PDF
Program Tabs
NC-Assistant
NC-Assistant
This section describes the options in the
NC-Assistant
tab.
The
NC-Assistant
in CIMCO Edit is a collective term for a range of options that help you streamline the coding process, making it faster and less prone to errors. Central to these options are the macro tools, which include an extensive array of predefined macros as well as the option for users to create their own.
These macros are key in allowing CIMCO Edit to identify specific lines or blocks within your code, facilitating swift updates through a dynamic interface. This interface, which aids in modifying parameter values, is conveniently accessible via the
NC-Assistant sidebar
. Here, users can also find a comprehensive list of macros, ensuring that these powerful tools are readily available for efficient coding.
Subsections
NC-Assistant
Macros
Info
Setup
Multi Channel
NC-Assistant Sidebar
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/info/
TITLE: Info
======================================================================
PDF
Program Tabs
NC-Assistant
Info
Info
This section describes the options in the
Info
menu which allow you to toggle the visibility of the NC-Assistant sidebar and the NC code balloons (tooltips).
Info menu.
Menu options
Hide Sidebar /
Ctrl+Shift+A
Click this option to show or hide the
NC-Assistant sidebar
.
Hide Balloons
When hovering the mouse over an NC code, a yellow balloon (tooltip) will show with an easy-to-read overview of the code parameters.
Click this option to show or hide the NC-Assistant balloons (tooltips).
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/macros/
TITLE: Macros
======================================================================
PDF
Program Tabs
NC-Assistant
Macros
Macros
This section describes the options in the
Macros
menu which allow you to select
File Type
,
Macro Group
and
Macro Name
.
Macros menu.
Menu options
File Type
Shows the current file type. Click this to select a different file type from the dropdown list. This dropdown does the same as the dropdown in the
File Type
menu in the Editor tab.
Macro Group
Shows the current
Macro Group
. Use this dropdown to select a different
Macro Group
.
Macro Groups
can be configured in the
Macro Setup
dialog.
Macro Name
Shows the currently selected macro. This is the macro that will be used when using the
Insert Macro
and
Find Macro
options in the
NC-Assistant
menu.
Click this dropdown to select a different macro.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/menuncassistantmultichannel/
TITLE: Multi Channel
======================================================================
PDF
Program Tabs
NC-Assistant
Multi Channel
Multi Channel
This section describes the options in the
Multi Channel
menu.
Multi Channel menu.
To use the Multi Channel options you must first configure
Multi Channel
in the Editor Setup for the specific File type.
The Multi Channel option enables you to simultaneously view an NC program for machines with two or more channels. Channels are displayed side-by-side in separate editor windows, and the feature also incorporates the synchronization provided by Wait codes.
Editing can be done in all channel windows and, by default,
Wait codes
that match are shown in yellow while missing wait codes are shown in purple.
Menu options
Window
Select this option to view the current program in Multi Channel mode.
Files
Select this option to view multiple files in Multi Channel mode.
Close
Select this option to close the Multi Channel view.
Next /
Ctrl+Down Arrow
Jump to the next synchronization point.
Previous /
Ctrl+Up Arrow
Jump to the previous synchronization point.
Synchronize Scrolling
Use this option to lock scroll all channels at the same time.
Pause Synchronization
Use this option to pause the automatic synchronization of all channels.
Setup Multi Channel
This option will open the
Multi Channel
configuration dialog in the Editor Setup.
You can also access the configuration using the icon
.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/nc-assistant/
TITLE: NC-Assistant
======================================================================
PDF
Program Tabs
NC-Assistant
NC-Assistant
NC-Assistant
This section describes the options in the
NC-Assistant
menu which allow you to insert, modify and find macros in your code.
The
NC-Assistant
menu is closely tied to the
Macros
menu beside it and the options
Insert Macro
and
Find Macro
both use the macro that is selected in the
Macro Name
dropdown in the
Macros
menu.
NC Assistant menu.
Menu options
Insert Macro
Inserts the macro that is selected in the
Macro Name
dropdown in the
Macros
menu.
A macro can also be inserted by double-clicking its name in the NC-Assistant sidebar or selecting it and clicking the
Add
button.
When inserting a macro, you need to enter two types of parameters:
The required parameters
The optional parameters (marked with *).
The parameter fields in the
Insert
dialog will change depending on the macro being inserted. Enter the parameters and click OK to insert the macro.
Insert Macro dialog.
Modify Macro
Modify the macro at the curser position.
To modify the values in an already inserted macro, position the mouse cursor on the macro-code (notice the
Modify Macro
icon in the Ribbon bar becomes active) and click the
Modify Macro
option.
The
Modify
dialog will appear in which you can update the macro parameter values. Click
OK
to apply the changes.
If default values have been defined for a macro, clicking the
Default
button will revert the values to their original, default values.
Please see the
NC-Assistant Sidebar
for an alternative to this option.
The Modify Macro dialog.
Find Macro
Search for the macro that is selected in the
Macro Name
dropdown in the
Macros
menu.
You can search for a macro in an NC program in two ways:
In the field
Cycles/Macros
, select the macro to search for and click the button
Find Macro
.
Select the macro to search for from the dropdown list and click on the icon
Find Macro
.
If you receive the message: _Cannot find the macro ..., it is because the desired macro was not specified as a macro. This can be the case if the NC text has been copied or created manually.
Macro Setup
Click this to enter the
Macro Setup
dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/setup/
TITLE: Setup
======================================================================
PDF
Program Tabs
NC-Assistant
Setup
Setup
This section describes the options in the
Setup
menu.
Subsections
Macro Setup Dialog
Formulas in Macros
Macro Setup menu.
Menu options
Record Macro
To create a macro from a specific or frequently recurring NC block, select the block in your NC program and then click on the
Record Macro
option.
The dialog
Add Macro
will appears in which you must name the new macro. Once you click the
OK
button to continue, the
Macro Setup
dialog will open for further configuration of the new macro.
Please refer to the
Macro Setup
dialog for further information.
Macro Setup
Opens the
Macro setup
dialog where you can configure, add, and modify macros for different file types. Please refer to the
Macro Setup
dialog for further information.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/setup/dialog/
TITLE: Macro Setup Dialog
======================================================================
PDF
Program Tabs
NC-Assistant
Setup
Macro Setup Dialog
Macro Setup Dialog
The
Macro Setup
dialog allows you to configure, add, and modify macros for different file types.
To import or backup your macros, locate the .MAC files that store the Macro configurations. These files can be found in the following directory:
%appdata%\CIMCO 2026\CIMCOEdit\Types\.
The dialog
Macro Setup
is divided into three functional areas that are described in details in the following sections.
Macro Setup dialog.
Area 1: List of macros
Machine Type
This drop-down menu provides a list of defined machine types you can select from (e.g. ISO Milling, ISO Turning, Heidenhain, etc.).
When the
Machine Type
is changed, the
Macro group
dropdown is updated with the available groups for the selected type.
Macro group
This drop-down menu provides a list of defined macro groups.
To create, rename or delete a macro group, click on the
Macro groups
icon
at the right on this field.
Edit Macro Groups dialog.
Macro name
Here you can see all available macros for the selected machine type and macro group.
Add
Click this button to open the dialog
Add macro
. Enter the name of the new macro and click
OK
. The new macro is added right after the selected macro in the
Macro name
list.
Rename
Click this button to rename the selected macro.
Copy
Click this button to make a copy of the selected macro.
You can make a few changes in the name and the contents of the macro to create a similar macro and save it.
Delete
Click this button to delete the selected macro.
It will display a confirmation message asking if you really want to delete the selected macro. If you answer
Yes
, the macro name and its contents will be deleted.
Copy To
Click this button to copy the selected macro to a different configuration.
The Copy Macros dialog will allow you to copy several macros at a time (check boxes at the left of the macro name) to the specified target Machine Type and Macro Group.
Copy Macros dialog.
Move To
Click this button to move the selected macro to a different configuration.
The functionality is similar to the
Copy To
button, but the selected macros are deleted from the original Machine Type and Macro Group.
Copy Group
Click this button to copy one or more
Macro Groups
from one File Type to another. This action opens the
Copy Macro Groups
dialog.
Within the dialog:
On the left side, select the File Type and the Macro Groups you wish to copy.
On the right side, choose the File Types to which you want to copy the selected groups.
In the
Duplicate Copy Behavior
dropdown, define the action to take if an identical
Macro Group
already exists in the target
File Type
. Your options are:
Skip duplicates:
The copy process will bypass any group that already exists in the target File Type.
Overwrite duplicates:
The process will replace the existing group in the target File Type with the one being copied.
Abort copy if duplicate:
Abort the copy process.
Copy Macro Groups dialog
Up / Down arrows
Use these buttons to move the selected macro up or down the list.
Use the larger arrow buttons to move the selected macro 10 places up or down the list.
Favorite
Use this button to favorite or un-favorite a macro.
When a macro is favored (star is glowing) it will show in the
Favorites
group. The favorite macro will show group name and macro name in the format:
{group}->{macro}.
Pressing the
Favorite
button when the favorite already exists will remove the favorite.
Area 2: Macro definition
Macro definition field
In the
Macro definition
section of the dialog, use the large text entry field (
Macro definition field
), on the right-hand side of the dialog, to enter the contents of the macro including text, variables and formulas.
The following options are available:
User (input) variables:
User variables are specified with a '$' character followed by a number in ascending order ($1, $2, $3, ect.). When selected, User variables can be configured in the fields under
Description
. User Variables can either be written directly or inserted using the button
Add User Input
. You can use the same variable multiple times in a macro.
System variables:
System variables are specified with a '$' followed by an uppercase variable name. System variables insert data/info from the system and cannot be modified. You can use the
Info variable
dropdown to see the available System variables and insert using the button
Add info
.
Formulas:
Formulas are specified with a '@' character followed by a number and an opening and closing bracket where the formula can be entered. Please refer to
Formulas in Macros
for further information.
Block numbers:
To add a block number to a line, specify a '#' at the beginning of the line. When the macro is inserted, # will be replaced with the correct block number value.
# character in front:
If you need to output a '#' as the first character in a string (which will be interpreted as a Block number by default), you can do this by entering '##' instead. This can be useful for Fanuc Macro B variables.
Character after variable:
If you need to insert a character right after a variable, you must insert a '|' (vertical bar) after the variable such as $2|100.
Start on new line:
If a macro
must
start on a new line, when inserted, add a blank line first in the macro definition field.
Please refer to the predefined macros in CIMCO Edit, such as
Program Start and End
to see examples of how macros can be configured.
Info variable
Use this dropdown menu to see a list of available
System variables
such as date, time, date and time, filename, etc. When a variable is selected from the list, insert it by clicking the button
Add Info
.
Add Info
Click this button to insert a System variable (selected in the
Info variable
dropdown list).
Add Formula
Click this button to insert a new formula.
Formulas are specified with a '@' character followed by a number and an opening and closing bracket where the formula can be entered.
Example
: @3{sqrt($1*$1 + $2*$2)}
Please refer to
Formulas in Macros
for further information.
Add User Input
Click this button to insert a new User variable such as $1, $2, $3, etc.
User Input Order
Click this button to arrange the order in which User variables are presented in the
Insert
dialog when adding the macro. This does not change the order of the variables when the macro is inserted in the NC program.
Clicking this button shows the following dialog. Use the up/down arrows to change the order of variables.
User Input Order dialog.
Area 3: Parameter configuration
Select or click a variable or formula in the
Macro definition field
to configure it using the fields and options in Area 3.
Description
Use this field to add a description of the selected parameter.
When you insert the macro into the CNC program by clicking the icon
, the
Insert
dialog will appears to let you enter all macro parameters. The description is shown next to the parameter field.
Macro parameter input fields (example).
Prefix
Use this field to specify a prefix string for the selected parameter, e.g. T for tool or S for spindle speed. This string or character will be added right before the value specified in the
Insert
dialog.
Suffix
Use this field to specify a suffix string for the selected parameter. Works the same way as
Prefix
but will be added right after the value specified in the
Insert
dialog.
Decimals
Use this dropdown to select the number of decimal digits.
As specified:
The number of decimals in the input and output will remain the same. Entering 10 will output 10. Entering 10.1 will output 10.1.
Any:
Will output at least 1 decimal. Entering 10 or 10. will both output as 10.0. Entering 10.123 will output as 10.123.
0 - 5:
Will output the number of decimals selected (0-5). If 3 is selected, entering 10 will output 10.000 (3 decimals). Entering 10.12 will output 10.120.
Always check the results of the formulas carefully to make sure you are getting the correct value and format.
Digits
Use this field to specify the number of digits. E.g. when inserting an O-number with 4 digits, the result becomes 'O0007'.
Min
Use this field to specify a minimum value for the selected parameter. If you enter a value lower than the
Min
value, you will immediately be prompted for correction.
Error message for value lower than
Min
.
Max
Use this field to specify a maximum value for the selected parameter. If you enter a value higher than the
Max
value, you will immediately be prompted for correction.
Default value
Use this field to specify a default value for the selected parameter.
Predefined values
Select this option if this macro parameter must be selected from a list of predefined values.
Click the button
Configure choices
to enter the specific values the user can choose from when inserting this macro parameter.
Predefined values setup dialog.
This dialog shows the list of values that will be available to select for the user when inserting the macro.
Label:
the text that will be displayed in the dropdown for the user to select.
Inserted value:
the value which will be inserted into the NC code output of the macro.
If
Label
is left blank, it will automatically be filled with the value. Double-click a Label-value pair to edit it. The pairs will appear in the dropdown in the same order as in this dialog with the top one selected as default.
Macro illustration / Parameter illustration
Use this field to specify a general macro image or a parameter image that will be shown in the
Insert
dialog. Click on a variable to specify a Parameter illustration in this field or click anywhere outside to add a general macro image.
Parameter illustration
will be shown when the input field for the parameter is active.
Macro illustration
will be shown when the input box for a parameter, which does not have a Parameter illustration defined, is active.
Click the
Select Picture
button
to select the desired picture for the macro/parameter, and the
No Picture
button
to remove the picture.
Macro attachment
Adding an attachment to a macro will show a button in the
Insert
dialog that, when clicked, will open the attachment. This can be used to associate a detailed help file to a macro.
Click the
Select attachment
button
to select an attachment for the macro, and the
Clear attachment
button
to remove the file.
Area 3: Parameter monitoring / Additional options
Use the checkboxes to enable or disable additional options.
The additional options must be selected carefully, as they affect the final result.
Parameter is required
Check this field if the user is required to specify a value for the selected parameter.
If you do not check this box, the sign * will appear in the parameter input field, indicating that this parameter is
optional
. In this case, you do not need to enter a value in the field. If you do it anyway, you will change the (modal) value for this NC code.
Optional Parameters
can for example be found at the 3 axes (X, Y, Z) of linear move (G01).
Insert with sign
Check this field if the parameter value should be inserted with a sign.
Example
: The value 123.4 will be inserted as +123.4.
Allow negative values
Check this field to allow negative values for the current parameter.
If you leave this field unchecked, only positive values will be accepted.
If you (accidentally) enter a negative value into the macro fields, the (-) sign will be ignored. The entered value will be considered as the absolute value of the parameter and will output positive NC codes in the CNC program.
Do not insert empty lines
Check this field if no blank line should be inserted when this parameter is not specified.
Allow letters
Check this field to allow the user to enter a text string.
According to ISO Convention, texts in the CNC program must be written in parentheses so they can be read on CNC machines. To prevent forgetting the brackets, these are generated automatically in CIMCO Edit 2026 when the field
Allow letters
is checked. Besides, the input fields
Min, Max, Decimals, Digits
and the box
Allow negative values
are grayed out.
Example:
The parameter $2 in the macro
Program Start and End
can include programmer initials, text strings, and special characters in parentheses.
Remember value
Check this field if the last value entered for this parameter should be used the next time the macro is called.
Example
: Let's assume you need to drill a blind hole into a special steel with three depths Z10, Z16 and Z20 at a defined location (X,Y). To achieve this, use the macro 'G81 Drilling cycle' and check the box
Remember value
for the parameters $1, $3, and $4. This way, those parameters will be automatically filled out with the previous settings for the blind hole machining. As we want to drill at different depths, we do not select
Remember value
for the parameter $2, which is the modal Z value of the operation. Since
Remember value
is not activated, the field $2 will be marked with an * and is initially empty.
If the drilling program was previously run and you now call the macro 'G81 Drilling cycle' by clicking the icon
, you just need to enter the first desired Z-value 10 into the field
Z coordinate (absolute)
and click on OK. Repeat the macro command with the Z-values 16 and 20, all other fields will be automatically filled out with the previously used values. Then you will have your blind hole.
Remember value
in macro G81.
Uppercase
If the option
Allow letters
is enabled and you want to write with capital letters, check this field to make the user input uppercase.
You must check this box if you want to use both lower and uppercase in the text.
Hide formula results (in entire macro)
When this field is checked, the results of NC-Assistant macro formulas are hidden.
Please refer to
Formulas in Macros
for more information.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/setup/formulas/
TITLE: Formulas in Macros
======================================================================
PDF
Program Tabs
NC-Assistant
Setup
Formulas in Macros
Formulas in Macros
CIMCO Edit can calculate and output values based upon a user input value. This has many uses and increases the power of the macro function.
CIMCO Edit 2026 includes predefined (sample) formulas that demonstrate the application of formulas within macros. To explore these, launch CIMCO Edit 2026 and choose
Formulas
from the
File Type
dropdown menu.
The sample file itself is located in the CIMCO Edit directory under \Samples\Formulas\formulas.MAC.
Sample formulas.
How to write a formula
The formulas are used much the same as variables, and are written @N as opposed to $N (with 'N' being a number), and allow the same formatting. To add a formula, enter the
Macro Setup
and click the
Add Formula
button. Write your formula inside the curly brackets { }.
Operators and Math Functions
+ (plus), - (minus), * (asterisk), / (forward slash) and % (for modulus)
Nested expressions using ( )
abs, acos, asin, atan, cos, cosh, floor, ln, log, sign, sin, sinh, sqrt, tan and tanh.
Only insert formula result
If you only want to insert the result of a formula into the NC program, simply create a one line macro and include all your user input values and calculations inside the formula expression { }. When inserting the macro, the
Insert
dialog will show the result of the calculation and you can click OK to insert it into you program.
Example: Circle area calculation
@2{PI*$1*$1}
This formula takes the user input value $1 and multiples it by itself and then multiplies it by Pi.
The
PI
math function is used here instead of entering 3.1416. Angles are in degrees.
Please use parenthesis ( ) for the input values in the trigonometric functions, e.g. sin($1)
Hiding the results of formulas
You can hide the results of formulas, which are shown in the
Insert
dialog as fields by default. This can either be set globally for all macros (under the
Editor Setup/General/NC-Assistant
) or individually for a macro (in the
Macro Setup
dialog).
Hide formula results globally by opening the
Editor Setup/General/NC-Assistant
dialog and selecting the checkbox
Hide NC-Assistant formula results
.
Hide formula results individually by opening the
Macro Setup
dialog and selecting the checkbox
Hide formula results (in entire macro)
for a specific macro.
If the
Hide NC-Assistant formula results
is selected in Editor Setup, it will override the option in the Macro Setup dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/sidebar/
TITLE: NC-Assistant Sidebar
======================================================================
PDF
Program Tabs
NC-Assistant
NC-Assistant Sidebar
NC-Assistant Sidebar
The NC-Assistant Sidebar streamlines the process of updating macro parameters, adapting swiftly to your selections within the NC code. It also displays a list of macros that correspond to the chosen
File Type
and
Macro Group
, simplifying the task of inserting macros whenever necessary.
You can toggle the visibility of the sidebar in the
info
menu.
NC-Assistant sidebar
NC-Assistant section
Dynamic Parameters List
Lists the parameter fields for the macro associated with the selected line or block. Changes in these fields are immediately reflected in your code.
Modify
Click the
Modify
button to open the
Modify Macro
dialog.
Cycles/Macros section
Cycles/Macros List
Lists the macros available for the currently selected
File Type
and
Macro Group
(see dropdown below). Click to select a macro or double-click to insert it in your code at the cursor location.
Macro Group
Use this dropdown to select a
Macro Group
.
Macro Groups
can be configured in the
Macro Setup
dialog.
Add
Click this to insert the selected macro in your code at the cursor location.
Find
Click this to find the next occurrence of the selected macro.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/
TITLE: NC Functions
======================================================================
PDF
Program Tabs
NC Functions
NC Functions
This section describes the options in the
NC Functions
tab.
Subsections
Block Numbers
Insert / Remove
Transform
Info
Scripts
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/blocknumbers/
TITLE: Block Numbers
======================================================================
PDF
Program Tabs
NC Functions
Block Numbers
Block Numbers
This section describes the options in the
Block Numbers
menu. This menu contains functions concerning the appearance of the CNC program. For instance the commands and the block numbers can be changed.
To configure numbering, please refer to the
Block Numbers
section in the Editor Setup.
Block Numbers menu.
Menu options
Renumber /
Ctrl+T
Inserts block numbers in the CNC program (or renumber the block numbers if some already exist in the CNC program).
If the option
Show quick setup
is enabled in the
Block Numbers
section in the Editor Setup, the following dialog will appear. This allows for swift configuration of the renumbering process.
Advanced Renumbering
Advanced Renumbering allows for more complex and nuanced renumbering of NC code.
Advance Renumbering dialog
Rule groups:
Allows you to save your renumbering setups for future use. Select a group from the
Rule groups
list to configure its settings or add a new group by selecting <Add>, entering a name in the empty field below, and clicking the Add button.
Control type:
Select the type of control. Different controls have different renumbering formats.
Start:
Enter the starting number.
Increment:
Enter how much to increment the numbering. If
Start
is set to 0 and
Increment
to 5, lines will be numbered 0, 5, 10, 15, etc.
Skip lines starting with:
Specify a list of characters or strings, separated by commas, that will instruct the renumbering process to skip a line. This ensures that lines
starting
with these specified prefixes are not renumbered. Examples could be O and %.
Skip lines containing:
Specify a list of characters or strings, separated by commas, that will instruct the renumbering process to skip a line. This ensures that lines
containing
these specified characters or strings are not renumbered.
Skip lines without block numbers:
ensures that any lines in the NC code that do not have block numbers are not renumbered. This feature is particularly useful when you want to maintain the sequence of numbered lines while ignoring those without numbers. When this option is checked, the renumbering process will continue on the next line that contains a block number, preserving the integrity of the code structure.
Rules:
Rules define specific conditions or patterns for the renumbering process and determine how and when the line numbers should be updated. For example, you might have a rule that renumbers lines only if they contain a certain command or pattern.
Trigger:
Triggers are the conditions that activate the rules. They are like the 'if' part of an 'if-then' statement. When a trigger condition is met in the NC code, the associated rule is applied. For instance, a trigger could be set to look for lines that contain a specific word or character sequence. An example of a
Trigger
could be 'G70' which a finishing cycle that often references specific line numbers or block numbers to indicate where the finishing cycle should begin and end.
Labels:
Labels are identifiers used within the NC code that can be referenced by rules and triggers. They often mark specific sections or commands in the code, such as loops or subroutines, and are essential for ensuring that the renumbering process respects the program's logic and structure. For the 'G70' example above,
Labels
could be P, Q where P might be used to indicate the start of a subprogram, and Q could be used to mark the end. Whenever the renumbering process encounters a G70 command, it should look for the associated P and Q labels to determine the range of lines to be renumbered. This ensures that the renumbering process respects the logical flow of the program and does not disrupt the execution of the finishing cycle.
Delete/Add buttons:
Select <Add> under
Rules
, fill out the
Trigger
and
Labels
fields, and click the Add button to add a new rule. Select an existing rule to delete it.
Result to new window:
Select this to create a new document with the renumbered NC program.
Remove
Deletes all block numbers from the CNC program.
Configure Block Numbering
Opens the
Block Numbers
configuration dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/info/
TITLE: Info
======================================================================
PDF
Program Tabs
NC Functions
Info
Info
This section describes the options under the
Info
menu. These can be used to calculate toolpath statistics and generate tool lists.
Info menu.
Menu options
Toolpath Statistics
Use this dialog to see detailed information about the CNC program's toolpaths. The range of X,Y,Z, machining time, tool change time, toolpath length, etc. Data can be exported or visualized in a graph.
Toolpath Statistics dialog.
The top part of the dialog shows information about each tool in the current NC program such as the min/max XYZ positions and total time. The details also show the minimum and maximum spindle speed. If the program has no spindle speed, they show N/A. When changing units, the
Tool change time
, or
Rapid speed
(in the lower part of the screen), this is immediately reflected in the data.
In the lower part of the dialog, you can set units,
Tool change time
,
Rapid speed
and configure what data to export. Make sure to select
All
or a specific tool in the list at the top.
Details for all tools:
Select the toolpath data you wish to export.
Toolpath unit:
Set Toolpath unit to either
Metric (mm)
or
Imperial (Inches)
.
Feedrate unit:
Set Feedrate unit to either
Unit/Min
or
Unit/Rev
.
Unit/Min:
This option sets the feedrate in units per minute, which is a common way to measure the speed at which the tool moves across the material surface.
Unit/Rev:
This option sets the feedrate in units per revolution, typically used in turning operations where the speed is determined by the number of units the tool moves per each rotation of the workpiece.
Tool change time:
Enter the average time taken for a tool change to accurately calculate total machining time.
Rapid speed (Unit/Min):
Enter the machine's rapid traverse rate to estimate non-cutting movement time.
Export format:
Select the export format:
Standard
or
CSV
. When clicking the
Export
button, a new document is created with the exported data.
Graph:
Open the
Toolpath Graphs
dialog. See below.
Setup:
Click this button to open the
Backplot
dialog in the
Editor Setup
.
Export:
Click this button to export the data. A new document will be created with the exported data.
Make Tool List
Create a tool list based on the current NC program. The tool list is created in a new document.
Combined Tool List
Create a combined tool list based on two or more open NC programs. The tool list is created in a new document.
Configure Tool List
Configure how the tool list is generated. Please refer to
Tool List
section in the
Editor Setup
for more details.
Toolpath Graphs
The
Toolpath Graphs
dialog is a useful tool that can help you catch mistakes and irregularities that might not be obvious when looking at the code alone.
The dialog shows a graph with a line for each axis. Horizontally the graph shows the movement over time and vertically, it shows the position of the cutting tool. Each line has its own color, making them easy to tell apart.
The graph shows the tools selected in the list at the top of the
Toolpath Statistics
dialog. Select
All
to show all tools. The graph stays open next to the dialog, and it updates when you select other tools.
Axes (X,Y,Z,A,B,C)
Use these buttons to toggle the visibility of axes in the graph.
Feedrate (F)
Use this button to toggle the visibility of Feedrate in the graph.
Values
Use this dropdown to select how to display tool position values (vertical).
Absolute:
displays the absolute position of the tool.
Delta:
displays the tool position relative to its last position.
Zoom
Use this dropdown to select the type of zoom. You can zoom in and out on the graph with the mouse scroll wheel.
Horizontal:
only zoom the graph horizontally
Vertical:
only zoom the graph vertically
2-Dimensional:
zoom the graph both horizontally and vertically
Close
Click this button to close the dialog.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/insert-remove/
TITLE: Insert / Remove
======================================================================
PDF
Program Tabs
NC Functions
Insert / Remove
Insert / Remove
This section describes the options in the
Insert / Remove
menu. These allow you to quickly write and edit NC programs.
Insert/Remove menu.
Menu options
Mark/Delete Range /
Ctrl+M
When clicking on
Mark/Delete Range
, the following dialog appears:
Mark/Delete dialog.
This dialog allows you to specify a range of lines or block numbers to be updated, selected or deleted. It is possible to make a special selection (or deletion) from a tool change, feedrate or spindle speed value up till the next.
You can also access this dialog from the
Edit
menu under the Editor tab.
Insert Block Skips
This adds a special skip-character to the start of lines. If no lines have been selected, the skip-character will be prepended to all lines. If lines have been selected, only those lines will get the character.
The block skip character can be defined in the
Machine configuration
dialog.
Remove Block Skips
This removes all the skip-characters from the current CNC program. Click the down arrow of the
Block Skips
option to access this option. If no lines have been selected, skip-characters will be removed from all lines. If lines have been selected, only those lines will get the skip-character removed.
Insert Spaces
Inserts space characters between the commands in the CNC program, where there is no space character between two commands. Existing space characters are left as they are.
Remove Spaces
Deletes all the space characters and tab signs from the CNC program (whitespace characters). Click the down arrow of the
Insert Spaces
option to access this option.
Remove Empty Lines
Removes all the empty lines from the NC program. Click the down arrow of the
Insert Spaces
option to access this option.
Remove Comments
Removes all the comments from the NC program - written in parentheses or with the
Comment start/end
characters defined in the
Machine configuration
dialog. Click the down arrow of the
Insert Spaces
option to access this option.
Insert Strings
Inserts a user-defined string in the document at the place defined in the dialog below.
Insert string dialog.
Insert string:
Specify the text string to be inserted into the document.
Where:
Choose the location in the document where the string will be inserted.
Insert at start of line:
The string will be added at the beginning of the selected line(s).
Insert at end of line:
The string will be appended to the end of the selected line(s).
Insert after block number:
The string will replace the specified block number.
Insert before matched string:
The string will be inserted immediately before the text that matches the specified string.
Insert after matched string:
The string will be placed immediately after the text that matches the specified string.
Insert on new line before matched string:
The string will be inserted on a new line before the line containing the matched string.
Insert on new line after matched string:
The string will be inserted on a new line following the line containing the matched string.
On lines matching string:
Define a specific string to target lines where the insertion will occur.
Regular Expression:
Use a regular expression pattern to match lines for more complex insertion criteria. See
Regular Expressions
for more information.
Remove Strings
Removes strings from the NC program according to the specifications entered in the
Remove String
dialog (similar to the
Insert Strings
dialog). Click the down arrow of the
Insert Strings
option to access this option.
Insert Monitoring Macros
Inserts monitoring macros in the NC program. Click the down arrow of the
Insert Strings
option to access this option.
When you select this option, the commands and values for program start, feedrate (F), spindle speed (S), and tool change (T) are automatically found in the NC program and inserted into lines starting with
DPRNT
right after the individual command.
The following images show a program before and after adding Monitoring Macros.
CNC program without monitoring macros.
CNC program with monitoring macros.
The observed values for the macros can be read via the serial interface for further processing.
Remove Monitoring Macros
Removes all DPRNT lines that were added using the
Insert Monitoring Macros
function and restores the NC program to its original. Click the down arrow of the
Insert Strings
option to access this option.
Uppercase /
Ctrl+U
Changes the case of the text to 'UPPERCASE' - including the comments.
Lowercase /
Ctrl+Shift+U
Changes the case of the text to 'lowercase' - including the comments.
Auto Insert Spaces
When this option is activated, a space is automatically inserted before each NC-word if the program is written "in a row" (without spaces).
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/scripts/
TITLE: Scripts
======================================================================
PDF
Program Tabs
NC Functions
Scripts
Scripts
This section describes the options in the
Scripts
group of the
NC Functions
tab. An NC Function script is a small program, written in JavaScript in a file with the extension
.ncjs
, that changes NC programs the way the built-in NC Functions do. It reads the program and returns changes, new programs or the program's setup file, and CIMCO Edit applies them. CIMCO Edit comes with example scripts, and you can write your own. How to write a script is described in
Writing NC Function Scripts
.
Scripts group.
NC Function scripts need the Ultra license. The Scripts group is not shown without it, or when advanced NC Functions are turned off in Setup.
Each script runs in a separate, protected process that can read nothing but the program CIMCO Edit gives it. It cannot read files, use the network or start other programs. Check the result of a script as you check any NC program.
Menu options
Run script
Run an NC Function script on the program or the selection. The menu lists your scripts, one submenu per subfolder of the scripts folder, and the submenu
Examples
with the example scripts. Point at a script to see its description, version and author. When you have no scripts yet, the menu says so.
Script setup
See what an NC Function script does and uses, and set whether it runs automatically. The menu lists the same scripts as
Run script
. See
Script setup
below.
New script...
Create a new NC Function script. See
New script
below.
Stop
Stop the script or long operation running on the active program. Nothing is changed by a script that is stopped. To stop a script running on another program, switch to that program's window first.
A script can also have its own button in the Scripts group (see
Add to Ribbon Bar
in
Script setup
). Click the button to run the script. Its drop-down has one item,
Setup
, which opens the script's Script setup.
Running a script
Select
Run script
and the script. A script without parameters runs at once, on the selection when there is one, otherwise on the whole program. A script with parameters opens a dialog first.
Parameters of the Arc fit example.
The dialog shows the script's description and its parameters. A parameter marked
Required
must be filled in, and the allowed range of a number is shown next to the field. The values you use are remembered for the script and the machine type.
Result to new window
Check this field to open the result in a new window and leave the program as it is. The field is always checked when the script writes new programs, or when the program is read-only.
Selection only
Check this field to run the script only on the selected lines. The field is available when lines are selected.
Compare with original
Check this field to compare the result with the original program in File Compare. The field is available when
Result to new window
is checked.
Default
Click this button to set the parameters back to the script's default values.
While the script runs, the program is locked and a progress bar is shown, as during a long NC Function. Up to four scripts can run at the same time, and a further one waits until one of them ends.
When the run ends with
You see
Changes
The program is changed as one Undo step, or the result opens in a new window. The status bar says how many lines were changed, and how many warnings the script gave.
No changes
The status bar says the script made no changes.
An error
A message names the first error and the line, in the script or in the program. Nothing was changed.
Stop
The status bar says the script was stopped. Nothing was changed.
Run script
is not available on a script document, on a compare or synchronized window, or while the program is busy.
Script setup
Select
Script setup
and the script, or
Setup
in the drop-down of the script's own button.
Script setup of the NC statistics comment example.
The title shows the script and the machine type the settings are for: the machine type of the active program, or the one selected in the machine type list when no program is open. The top of the dialog shows the script's description, author, version, what its output is, what it asks CIMCO Edit about (
Uses
) and which files it writes.
Output folder
Use this field to specify the folder where the script writes the programs it makes. Leave it empty to open the results in new windows. The field is only shown for scripts that write new programs.
Run automatically
Check this field to run the script automatically on programs of this machine type. It is off for every script until you check it. See
Running scripts automatically
below.
When
Use this field to select when the script runs automatically:
When a program is opened
,
When the backplot or a simulation of a program starts
, or both.
Parameters
Use these fields to set the parameter values that automatic runs use. They are saved apart from the values of the parameter dialog. When a value is not set, the script's default is used.
Add to Ribbon Bar
Check this field to give the script its own button in the Scripts group. You are asked for an icon file (
.xaml
) at once. The button is added, or removed, the next time CIMCO Edit starts. This setting is the same for every machine type.
Icon
The icon file of the script's button. Click the button next to the field to choose another
.xaml
file. A file the Ribbon cannot draw is refused.
Edit script
Click this button to open the script as a script document. An example opens read-only. Saving it saves a copy in the scripts folder.
Delete script
Click this button to delete the script. You are asked first. The file is moved to the Recycle Bin, and the script's settings are removed for every machine type. Examples cannot be deleted. A script that is open with unsaved changes, or still running, cannot be deleted.
OK
saves the settings. It does not run the script.
The output folder,
Run automatically
,
When
and the parameter values are saved for the machine type in the title, so a script can run for one machine type and not for another, or with other values.
Running scripts automatically
A script that runs automatically runs on the whole program, without any dialog, when its
When
happens. A script can first check whether the program needs it, and when it does not, nothing happens. Automatic runs follow these rules:
A script that changes the program changes it in place, as one Undo step. The program is marked as changed, and nothing is saved by the script.
A script that writes new programs opens them in new windows, or writes them to its output folder. A file that is already there is never replaced.
When the script runs as the backplot or a simulation starts, the program is locked until the script ends, and the backplot or simulation then starts, also when the script failed.
An automatic run may take up to 60 seconds.
Stop
on the program's window stops it. Up to two automatic runs work at the same time.
When an automatic run fails, a message names the script, the program and the first error. Nothing in the program was changed. To stop a script that keeps failing, clear
Run automatically
in its Script setup.
Scripts do not run automatically on untitled or read-only programs, programs from NC-Base or a DNC receive, script documents, compare and synchronized windows, and programs of text machine types.
When a machine type is copied, imported or replaced by a file from somewhere else, it brings the script settings along, but no script is turned on. Check
Run automatically
again for that machine type.
New script
Select
New script...
to start a new script. The dialog has these fields:
Name
Use this field to specify the name of the script. It is the name shown in the menus and the file name. A name cannot contain any of the characters \ / : * ? " < > | & [ ] = ;
Folder
Use this field to select the folder of the script: the scripts folder itself, or one of its subfolders. You can type the name of a new subfolder. The name
Examples
cannot be used.
Start from
Use this field to select what the new script starts from: a blank script with comments that explain the parts of a script, one of the examples, or the script document that is open.
Description
below shows what the selected script does, and
Saved as
shows the file the script is saved to.
OK
opens the new script as a script document. Nothing is written until you save it. When you save a script, CIMCO Edit reads it at once, and errors in it are listed in the
Script results
window, with their line. Double-click a row to go to the line. Then try the script with
Run script
on a program. Undo takes the change back.
Installing a script someone sent you
When you open a
.ncjs
file that is not in the scripts folder, for example from an e-mail, the
Install NC Function
dialog shows what the script does, its author and version, its output, what it uses and writes, and whether it runs automatically. A status line says whether the script is new, the same as, newer or older than one you have, or has the name of a script by another author.
Install as
Use this field to specify the name the script is installed under. Use
Folder
to select the folder.
Install
Click this button to copy the script into the scripts folder.
Open without installing
Click this button to open the script as a script document, to read or edit it.
An installed script does not run automatically until you check
Run automatically
in its Script setup. When it replaces an installed script that runs automatically, that setting stays on.
Where scripts are stored
Your scripts are in the scripts folder, the folder
NCSCRIPTS
in the CIMCO Edit data folder, and in its subfolders one level down. The examples are in the folder
NCScripts
in the installation folder. The menus list up to 64 of your scripts and 32 examples. A script is known by its name and folder, so a script you rename or move in Windows Explorer loses its settings.
When a script does not run
Problem
Check
There is no Scripts group
The Ultra license, and whether advanced NC Functions are turned off in Setup.
A script is not in the menu
It is more than one subfolder down, in a folder named Examples, after the first 64 scripts, or not a
.ncjs
file.
The menu item is not available
The active window is a script document, a compare or synchronized window, or the program is busy.
It did not run automatically
Run automatically
is not checked for the program's machine type,
When
is another event, the script found that the program does not need it, a required parameter has no value, or the program is one that scripts do not run on.
The run failed
The message names the first error and its line. Open the script with
Edit script
in Script setup and save it, to list every error.
Its button is missing
Add to Ribbon Bar
is not checked, CIMCO Edit has not been restarted since, or the script's file is gone.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/scripts/writing-scripts/
TITLE: Writing NC Function Scripts
======================================================================
PDF
Program Tabs
NC Functions
Scripts
Writing NC Function Scripts
Writing NC Function Scripts
This section describes how to write an NC Function script: the parts of a script file, what a script can read and change, and the limits. How to run scripts and set them up is described in
Scripts
.
Scripts are written in JavaScript. Write them in the ES5 version of JavaScript (
var
and
function
, no
let
,
const
, arrow functions, classes or template strings), so they also run in older versions of CIMCO Edit. The
run
and
condition
functions cannot be
async
.
The easiest way to start is
New script...
with
Start from
set to
Blank script
, which has comments that explain each part, or to one of the examples.
The script file
A script defines
info
and
run
, and may define
condition
. Code outside these functions runs each time CIMCO Edit reads the script (to list it and show its settings), so it must not do long work. Reading a script is stopped after 2 seconds.
var info = {
 api: "1.1",
 description: "Writes the program's toolpath statistics as a comment at the top.",
 author: "CIMCO A/S",
 version: "1.0",
 output: "replace",
 uses: ["toolpath_statistics"],
 triggers: ["fileOpen"],
 params: [
 { id: "perTool", label: "One line per tool", type: "bool", default: true }
 ]
};
function condition(doc, p, context) { /* true or false, automatic runs only */ }
function run(doc, p, nc, out) { /* read doc, write with out */ }
info
Field
Meaning
api
The script API version the script needs: "1.0", or "1.1" for
uses
,
writes
and
triggers
. A script that needs a newer version than CIMCO Edit has is refused.
description, author, version
Shown in the parameter dialog, Script setup, New script and the install dialog. The version is compared as numbers separated by dots when a script is installed over another.
output
"replace" (the default) changes the program in place. "new" opens the changed program in a new window.
outputs
A list such as [{ machineType: "Heidenhain Milling" }]. The script writes new programs for these machine types with
out.document
, instead of changing the program.
params
The fields of the parameter dialog, at most 40 (see below).
uses
What the script asks CIMCO Edit about (see
Asking the editor
). Shown as
Uses
in Script setup. Any other question is refused.
writes
["setup"] when the script writes the program's setup file. Shown as
Writes files
.
triggers
["fileOpen"], ["backplot"] or both: when the author means the script to run automatically. It does not limit the user, who picks
When
in Script setup.
description
and
label
can also be given per language, as { "en": "...", "de": "..." }. CIMCO Edit shows the current language, otherwise English.
params
Field
Meaning
id
The name of the value in
p
(for example
p.tolerance
): a letter or
, then letters, digits and
. Each id is used once.
label
The label of the field in the dialog. Two fields cannot have the same label, and the labels of the dialog's own fields (Result to new window, Selection only, Compare with original) cannot be used.
type
"number", "text", "choice" (with
choices: [...]
) or "bool".
default
The value before the user changes it. Automatic runs use it when Script setup holds no value.
required
The field must be filled in. Shown as
Required
.
min, max
The allowed range of a number, shown next to the field.
decimals
How many decimals a number field shows.
The script gets a number as a number (a typed comma is read as a decimal point), a choice as its text and a bool as true or false. An empty field that is not required gives NaN for a number and an empty text for text.
run(doc, p, nc, out)
CIMCO Edit calls
run
once for each run. Nothing in the program changes until
run
returns without an error, and an error anywhere changes nothing.
doc, the program
Member
Meaning
doc.lines
The program's lines as texts (the script's own copy).
doc.blocks
The blocks of the program, each with its text, its first line number and its number of lines. Lines joined by the machine type's line extender form one block.
doc.first, doc.last
The line numbers of the first and last line. A run on a selection gets only the selected lines.
doc.continues
True when the program has lines after doc.last, in a run on a selection that ends before the program does. A script that changes a modal state must leave it as the program had it at the end, because the next line is not the script's to change.
doc.line(n)
The text of line n.
doc.fileName
The program's file path, none for an untitled program.
doc.machineType
The name of the machine type.
doc.options
Settings of the machine type: unit ("mm" or "inch"), turning, diameterProgramming, diameterArcCenter, arcCenter, arcTolerance, incrementalWords, letterMap, dialect ("iso", "siemens", "heidenhain"), defaultPlane (17 or 18) and decimals.
doc.syntax
The comment characters and block skip of the machine type.
doc.files.setup
For a script that declares writes: ["setup"], the text of the program's setup file, or null.
Line numbers are always the program's own line numbers, as the editor shows them.
nc, helpers
Member
Does
nc.words(block)
The address words of a block or line: address, text, value and position. The value is NaN when it is a parameter or an expression. Comments and skips are not words.
nc.tokens(block)
All parts of a block: words, numbers, parameters, comments, strings, skips and operators.
nc.format(value, options)
A number written as the machine type writes it (decimals, trailing zeros, decimal point, plus sign).
nc.warn(line, message)
A warning on a program line. The run still succeeds, and the status bar counts the warnings.
nc.error(line, message)
Stops the run with an error on a program line. Nothing is changed.
nc.log(...)
Writes a line to the run's log.
nc.status(text)
The text of the status bar when the run ends, in place of the editor's own.
nc.progress(fraction)
0 to 1 for the progress bar of a long run.
nc.trigger
null in a run by hand. In an automatic run it says whether the program was opened ("fileOpen") or its backplot or a simulation starts ("backplot").
nc.iso
A reader of ISO programs (Fanuc, Haas, Mazak EIA, Okuma, Mitsubishi, Siemens in ISO mode) that keeps the modal state and the position. The arc examples use it.
out, the result
Call
Does
out.set(line or block, text)
Replaces a line, or a whole block.
out.remove(line or block)
Removes it.
out.insertBefore(line or block, text), out.insertAfter(line or block, text)
Inserts lines.
out.document({ name, machineType, lines })
For scripts with
outputs
: one new program.
name
is a file name without a folder.
out.file({ setup: true, text })
Writes the program's setup file, once for each run. The script must declare writes: ["setup"].
text
is a text, which is split at its line breaks, or a list of lines. The changes refer to the program as it was, in whatever order they are made, and are applied together as one Undo step.
condition(doc, p, context)
Only automatic runs call
condition
, before
run
. It returns true to run, or false to do nothing and show nothing.
context
is the same as
nc.trigger
. Use it to limit a script to the programs that need it, for example by machine type, or by looking for the script's own comment in the program.
Asking the editor
Inside
run
and
condition
a script with api "1.1" can ask CIMCO Edit about the program it runs on, for each name it lists in
info.uses
. A refused or failed question throws an error that the script can catch.
Call
Name in info.uses
Answer
editor.state()
get_state
The program's path, machine type, unit, lines, whether it is changed or read-only, its setup file, and whether its simulation is open.
editor.machineType()
machine_type
The program's machine type.
editor.statistics(args)
toolpath_statistics
The figures of Toolpath Statistics: times, lengths, ranges and tools.
editor.simulation(args), editor.simulationReport()
simulation
Questions about the program's open simulation, and its report.
editor.toolSetup(args)
tool_setup
The tools of the open simulation as setup file text.
editor.simulationCheck(args)
simulation_check
Runs the collision and limit check of the program's simulation and returns the report. With no simulation open, the check runs in the background and nothing is shown.
A script cannot run another script, change settings, run commands or change other programs.
The setup file
A script that declares writes: ["setup"] writes the program's setup file with
out.file
. The file goes where the simulation reads it, as the machine type's setting says.
doc.files.setup
holds the existing file, so the script can keep what it does not change. The program must have a file name, so save it first. When the file exists and is different, a run by hand asks before it replaces it, and an automatic run replaces it. With
Save backup file
on in Setup, the old file is kept with the extension
.setup.bak
. Undo removes the change to the program, not the file.
Limits
Limit
Value
Reading the script
2 seconds for the code outside
run
and
condition
.
Memory
512 MB for each run.
Time
None for a run by hand (use Stop). 60 seconds for an automatic run.
Parameters
40 for each script.
Scripts
64 of your own scripts in the menus.
The examples
Example
What it does
Parameters
Arc fit
Replaces runs of G01 moves by G02/G03 arcs that stay within the tolerance of the original path.
Tolerance, Minimum moves per arc, Maximum radius, Arc format, Fit helical arcs
Linearize arcs
Replaces G02/G03 arcs by the fewest G01 lines within the tolerance. Arcs with cutter compensation are left, with a warning.
Tolerance
Fanuc to Heidenhain Klartext
A sample converter to read and adapt: writes a Fanuc milling program as a new Heidenhain Klartext program. Blocks it cannot convert are kept as comments, with a warning.
None
NC statistics comment
Writes the toolpath statistics as a comment at the top of the program, in place of an earlier one.
One line per tool
Collision and limit report comment
Runs the collision and limit check of the program's simulation and writes the result as a comment at the top.
Report lines to list, Run in background
Tolerances are in the program's unit. Arc fit, Linearize arcs and NC statistics comment do not run on Heidenhain Klartext programs. On a selection, Arc fit and Linearize arcs change nothing until the selection sets G90 or G91, the plane and the cutter compensation, and say so in a warning. Start the selection at a line that sets them, or run on the whole program.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/transform/
TITLE: Transform
======================================================================
PDF
Program Tabs
NC Functions
Transform
Transform
This section describes the options in the
Transform
menu. These allow you to quickly adjust feedrate, spindle speed and make mathematical changes to your NC program.
Transform menu.
Menu options
Adjust Feedrate
Use this dialog to adjust the feedrate of the current NC program. To do this, click and drag the slider or enter the new feedrate directly in the field
New feedrate
. Click
OK
to apply the changes or
Cancel
to close the dialog.
Adjust feedrate dialog.
New feedrate:
Enter the percentage by which the feedrate should be changed.
Decimals:
Enter the number of decimals to the right of the decimal point.
Minimum value:
Enter the minimum feedrate (in mm/min).
Maximum value:
Enter the maximum feedrate (in mm/min).
When equal/greater than:
Only values equal to or greater than the value entered here will be modified.
When equal/less than:
Only values equal to or less than the value entered here will be modified.
Result to new window:
Check this field if the result of the operation should be shown in a new document.
Selection only:
If the
Selection only
option is also checked, only the selection is put into the new document.
Adjust spindle speed
Use this dialog to adjust the spindle speed of the current NC program. To do this, click and drag the slider or enter the new spindle speed directly in the field _New spindle speed. Click
OK
to apply the changes or
Cancel
to close the dialog.
Adjust spindle speed dialog.
New spindle speed:
Enter the percentage by which the feedrate should be changed.
Decimals:
Enter the number of decimals to the right of the decimal point.
Minimum value:
Enter the minimum spindle speed (in rev/min).
Maximum value:
Enter the maximum spindle speed (in rev/min).
When equal/greater than:
Only values equal to or greater than the value entered here will be modified.
When equal/less than:
Only values equal to or less than the value entered here will be modified.
Result to new window:
Check this field if the result of the operation should be shown in a new document.
Selection only:
If the
Selection only
option is also checked, only the selection is copied to the new document.
Simple math functions
Use this dialog to perform simple mathematical functions on the parameters in the current NC program.
Simple math functions dialog.
Parameter(s):
Select the checkboxes of the parameters that should be changed.
Other:
Select this option to enter parameters with more than one character. This enables the input field on the left where special characters (Ó, Ö, Ø...) or multi-digit (ABC) parameter names can be entered.
Addition (+):
Adds the specified value to all selected parameters.
Subtraction (-):
Subtracts the specified value from all selected parameters.
Multiplication (X):
Multiplies all selected parameters by the specified value.
Division (/):
Divides all selected parameters by the specified value.
Value:
Use this field to enter the value that will be inserted in the mathematical function (Addition / Subtraction / Multiplication / Division).
Maximum value:
Enter a maximum value. Parameters with values higher than specified here, after performing the mathematical function, will be set to this maximum value.
Minimum value:
Enter a minimum value. Parameters with values lower than specified here, after performing the mathematical function, will be set to this minimum value.
Decimals:
Enter the number of decimals to the right of the decimal point.
Keep decimals:
Select this field to provide the new value with the same number of decimals as the original value.
Strip trailing 0's:
Select this field to remove all zeros from the end of the number.
Strip leading 0's:
Select this field to remove all zeros from the beginning of the number.
Ignore case dropdown:
Select if only parameters in uppercase or lowercase should be changed, or select
Ignore case
to change parameters no matter their case.
Result to new window:
Check this field if the result of the operation should be shown in a new document.
Selection only:
If the
Selection only
option is also checked, only the selection is copied to the new document.
Translate
Use this dialog to translate the outline. The outline is moved to a position offset by the values entered in the
Translate (X,Y,Z)
fields.
Translate dialog.
Translate (X,Y,Z):
Enter the X, Y, and Z values to offset the outline.
Arc type:
Specify the arc type by selecting one of the four different types:
Auto detect
: Default.
Relative to start
: Relative to the initial coordinates of the contour.
Relative to end
: Relative to the end coordinates of the contour.
Absolute arc center
: Relative to the absolute center of the arc.
Strip trailing 0's:
Select this to remove all zeros from the end of the number.
Assume G91:
Select this when the control is preset for relative coordinates (G91).
Decimals:
Enter the number of decimals to the right of the decimal point.
Comma as decimal symbol:
Select this to use a comma as decimal separator.
Non-modal X/Y/Z:
Select this to use non-modal X/Y/Z values.
Result to new window:
Check this field if the result of the operation should be shown in a new document.
Selection only:
If the
Selection only
option is also checked, only the selection is copied to the new document.
Rotate
Use this dialog to rotate the outline around a specified point and with a specified angle. Click
OK
to apply the changes or
Cancel
to close the dialog with no changes.
Rotate dialog.
Point (X,Y):
Enter the coordinates of the center of the rotation in these fields.
Angle:
Enter the angle of rotation by degrees in this field.
Arc type:
Here you can specify the arc type by selecting one of the four different types:
Auto detect
: Default.
Relative to start
: Relative to the initial coordinates of the contour.
Relative to end
: Relative to the end coordinates of the contour.
Absolute arc center
: Relative to the absolute center of the arc.
Assume G91:
Select this when the control is preset for relative coordinates (G91).
Strip trailing 0's:
Select this to remove all zeros from the end of the number.
Decimals:
Enter into this field the number of decimals to the right of the decimal point.
Comma as decimal symbol:
Select this to use comma as decimal separator.
Reverse tool path:
Select this to reverse the trajectory of the tool path.
Result to new window:
Check this field if the result of the operation should be shown in a new document.
Selection only:
If the
Selection only
option is also checked, only the selection is copied to the new document.
Mirror
Use this dialog to mirror the outline around a specified line. Click
OK
to apply the changes or
Cancel
to close the dialog with no changes.
Mirror dialog.
Turning Program:
Select this option for turning operations. This will disable the
Point
and
Angle
fields below (the user-defined mirror axis).
Point (X,Y):
Enter the coordinates of the point of the mirror axis.
Angle:
Enter the angle of rotation by degrees of the mirror axis.
Arc type:
Specify the arc type by selecting one of the four different types:
Auto detect
: Default.
Relative to start
: Relative to the initial coordinates of the contour.
Relative to end
: Relative to the end coordinates of the contour.
Absolute arc center
: Relative to the absolute center of the arc.
Assume G91:
Select this when the control is preset for relative coordinates (G91).
Strip trailing 0's:
Select this to remove all zeros from the end of the number.
Decimals:
Enter the number of decimals to the right of the decimal point.
Comma as decimal symbol:
Select this to use comma as decimal separator.
Reverse tool path:
Select this to reverse the trajectory of the tool path.
Result to new window:
Check this field if the result of the operation should be shown in a new document.
Selection only:
If the
Selection only
option is also checked, only the selection is copied to the new document.
Tool compensation
Use this dialog to configure toolpath compensation (offset) for the current program. From the programmed workpiece contour to the left (G41), or to the right (G42), based on the direction of feed, in order to compensate different tool sizes.
Offset/Tool compensation dialog.
Offset:
Enter the offset value into this field.
Offset Left (G41):
Enable compensation of the milling path, offset left (G41).
Offset Right (G42):
Enable compensation of the milling path, offset right (G42).
Arc type:
Specify the arc type by selecting one of the four different types:
Auto detect
: Default.
Relative to start
: Relative to the initial coordinates of the contour.
Relative to end
: Relative to the end coordinates of the contour.
Absolute arc center
: Relative to the absolute center of the arc.
Strip trailing 0's:
Select this to remove all zeros from the end of the number.
Assume G91:
Select this when the control is preset for relative coordinates (G91).
Decimals:
Enter the number of decimals to the right of the decimal point.
Comma as decimal symbol:
Select this to use comma as decimal separator.
Non-modal X/Y/Z:
Select this to use non-modal X/Y/Z values.
Result to new window:
Check this field if the result of the operation should be shown in a new document.
Selection only:
If the
Selection only
option is also checked, only the selection is copied to the new document.
Heidenhain / ISO Converter
Use this option to convert Heidenhain CNC programs to ISO programs, or ISO programs to Heidenhain CNC programs.
Convert NC code
Use this option to convert from one NC format to another. You will need a converter file, also known as a Post Processor, for the target format.
NC Converter dialog
Choose original NC format:
Select the NC format to convert from.
Choose converter:
Select the converter/post processor file (.conv) for the NC format to covert to. CIMCO Edit includes some converters located in the \Converters folder in the program folder.
Convert to NCI format:
Select this to convert the NC code to NCI, a generic or intermediate format that represents toolpaths before they are converted into the final NC code by a post processor.
Use longhand cycles:
Select this to output each movement or cycle as individual lines of code, rather than using shorthand or canned cycles.
Result to new window:
Check this field if the result of the operation should be shown in a new document.
Selection only:
If the
Selection only
option is also checked, only the selection is copied to the new document.
Show Windows Calculator
Click this option to open the Windows® calculator.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.