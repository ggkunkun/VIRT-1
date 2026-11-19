# 官方语料摘录 B_backplot_sim（共 74 页，源自 docs.cimco.com/en/docs/edit/2026/）


======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/
TITLE: Backplot
======================================================================
PDF
Program Tabs
Backplot
Backplot
This section describes the options in the
Backplot
tab.
Please refer to the
Simulation
section for information about everything related to simulation in CIMCO Edit 2026.
Subsections
Backplot
View
Toolpath
Tool
Geometries
Control Type
Other
Find
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/file/
TITLE: Backplot
======================================================================
PDF
Program Tabs
Backplot
Backplot
Backplot
This section describes the options in the
Backplot
menu which are used for simulation and general backplot settings.
Backplot menu.
Menu options
Backplot /
Ctrl+Shift+P
Select this option to simulate the current NC program. The simulation window will open where you can see the NC program (left), the simulation (center) and the docking pane with the
Geometry Manager
(right) simultaneously.
Machine Simulation
Select this option to simulate the current NC program in Machine Simulation.
Machine Simulation is an add-on for CIMCO Edit 2026. You will only see this option with a valid license for Machine Simulation installed. See
Machine Simulation
for further information.
Backplot File
Enables you to backplot a file directly from disk, without opening the file first. When using this function the NC code will not be shown simultaneously.
Click the dropdown arrow below the icon to display a list of recently opened programs.
Close Backplot /
Ctrl+Shift+Q
Use this option to close the simulation window / backplot.
Backplot Setup
Click this to enter the
Backplot configuration
dialog in the Editor Setup.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/filetype/
TITLE: Control Type
======================================================================
PDF
Program Tabs
Backplot
Control Type
Control Type
This section describes the options in the
Control Type
menu which are used for setting the
Control Type
,
Machine Setup
and see supported axes.
The
Machine
(Machine Setup) must be selected before starting Backplot or Machine Simulation.
Control Type menu.
Menu options
Control Type
Use this dropdown to select the control type on the machine you wish to simulate.
Control Type for specific file types can be configured in the
Backplot
section in the Editor Setup.
Machine (Machine Setup)
Use this dropdown to select the machine setup you wish to simulate.
Machine setup for specific file types can be configured in the
Backplot
section in the Editor Setup.
Axes support (X, Y, Z, A, B, C)
Indicates the axes that are supported by the currently selected
Machine Setup
.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/find/
TITLE: Find
======================================================================
PDF
Program Tabs
Backplot
Find
Find
The Find section contains functions for searching (and replacing) through the active file.
Find menu.
Find Previous
,
Find Next
and
Go to Line/Block Number
are in the drop-down of
Find
.
Menu options
Find /
Ctrl+F
This option is similar to
Find
under the
Editor
tab.
Find Previous /
Shift+F3
This option is similar to
Find Previous
under the
Editor
tab.
Find Next /
F3
This option is similar to
Find Next
under the
Editor
tab.
Go to Line/Block Number /
Ctrl+J
This option is similar to
Go to Line/Block Number
under the
Editor
tab.
Next Tool Change
This option is similar to
Next Tool Change
under the
Editor
tab.
Previous Tool Change
This option is similar to
Previous Tool Change
under the
Editor
tab.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/other/
TITLE: Other
======================================================================
PDF
Program Tabs
Backplot
Other
Other
The Other menu contains functions for entering full screen, DXF export, and simulation control type.
Other menu.
Menu options
Full Screen
Select this option to show the simulation window in full screen. Use the
Escape
key or right-click menu in the simulation window to exit full screen.
Export as DXF File
Select this to export the toolpath data in DXF format. DXF is short for Drawing Exchange Format or Drawing Interchange Format and is a type of vector file.
DXF export can be configured in the
Other
section in the Editor Setup.
Save Presentation
Select this option to export the entire simulation for viewing as a 'stand-alone' simulation without needing CIMCO Edit.
You can save a presentation in two ways:
Simulation File:
Only includes the simulation
Presentation Bundle:
Includes both the simulation and the
Presentation Viewer application
(can also be used to send the simulation setup to CIMCO support)
The Presentation Viewer viewer application only have to be installed once and can then be used to view different simulations exported from CIMCO Edit.
Simulation files only contain simulation data and are useful for storing alongside other documents related to an NC program such as setup sheets and tool lists. They also have a relatively small filesize making them easy to share.
Other Settings
Select this option to open the
Other
setup dialog in the Editor Setup.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/solid/
TITLE: Geometries
======================================================================
PDF
Program Tabs
Backplot
Geometries
Geometries
This section describes the options in the
Geometries
group, which show and hide the workpiece, the fixture and the solid model of the stock, and are used for simulation of a solid model.
Geometries group.
Menu options
Workpiece
Click this option to show or hide the workpiece.
Click the down arrow and select
Add Workpiece
to add a workpiece, which enables part collision checks and
Stock Compare
.
Fixture
Click this option to show or hide the fixture.
Click the down arrow and select
Add Fixture
to add a fixture geometry.
Solid Model
Click this option to show or hide the solid model of the stock.
Click the down arrow for
Add Stock
and its options and for
Simulate
, which are described below.
Add Stock
Click on this icon to insert a rectangular stock model.
CIMCO Edit will insert a default stock model based on the toolpath data in the NC program. The stock model can be located in the
Geometry Manager
where its dimensions and other properties can be customized. By default, this option is similar to the
Dimensions
option below.
If stock model scanning is enabled in the Editor Setup under
Scanning
the behaviour of the
Add Stock
option will be different. In this case, stock type and dimensions can be scanned (imported) automatically from either the NC program or a Setup file associated with the NC program. This depends on how Scanning is configured.
Please refer to
Scanning
for further information about how to configure this.
Click the down arrow to see additional options.
Add Stock
This option is the same as the
Add Stock
above.
Dimensions
Select this option to insert a rectangular stock with dimensions based on the toolpath data alone.
In the
Geometry Manager
under
Properties
, the stock is defined by a height, width and length which is centered on a position in XYZ relative to an origin.
This option does not use
Scanning
.
Min/Max
Select this option to insert a rectangular stock with dimensions based on the toolpath data alone.
In the
Geometry Manager
under
Properties
, the stock is defined by two points; a
Lower Corner
and an
Upper Corner
. Both points are defined relative to a position in XYZ.
This option does not use
Scanning
.
Cylinder
Select this option to insert a cylinder shaped stock with dimensions based on the toolpath data alone.
In the
Geometry Manager
under
Properties
, the stock is defined by a center position, diameter and height. You can further define its
Axis
and
Origin
.
This option does not use
Scanning
.
STL
Select this option to load and insert the stock from an STL file. Simply click the option, locate and open the STL file. It will then be inserted into the simulation and show in the
Geometry Manager
.
This option does not use
Scanning
.
DXF
Select this option to load and insert the stock from an DXF file. Simply click the option, locate and open the DXF file. It will then be inserted into the simulation and show in the
Geometry Manager
.
This option does not use
Scanning
.
Simulate
This option requires that a stock model has been added.
Fast version
Enable this option to continuously update the solid model of the stock during simulation playback to reflect the expected machining outcome. Stock is also updated to reflect changes made in the Geometry Manager.
Disable this option to stop the stock from updating.
Standard version
When using the
Standard version
simulation, the stock is always updated to reflect the expected machining outcome. This cannot be disabled.
However, if you move the simulation backwards to an earlier point in your NC program, the stock will not update to reflect this. This is by design.
Click this option to regenerate (refresh) the solid model of the stock based on the current position in the NC program. This can also be done by right-clicking the stock in the
Geometry Manager
and selecting
Regenerate
.
If you make changes to the stock in the Geometry Manager, a red wireframe will show instead to indicate the stock must be regenerated. Do this the same way as described above.
Stock Compare
Select this option to compare the stock to a design model (Workpiece). The stock is color-coded based on its distance to the design model to easily identify any inaccuracies, whether too much stock has been removed (the tool gauges the design model) or where not enough stock has been removed.
Red color indicates areas where the stock has been over-machined and too much material has been removed
Blue color indicates areas where the stock has been under-machined and too little material has been removed
Green color indicates the stock is within tolerance
Hover the mouse over the colored stock to see the distance to the design model in different areas
To use Stock Compare it is necessary to set up both the Stock and a Workpiece in the
Geometry Manager
. The Workpiece should be an STL model representing the desired final product for comparison with the machined stock.
Under the
Simulation tab
in the docking pane (right side of screen), you can change the default Stock Compare settings for
Compare range
and
Stock to leave
.
Stock to leave
is the expected difference. For example, if you expect to leave 1mm of material for a later process, you can set this to 1.
Compare range
refers to the tolerance range within which the stock is considered to be machined correctly. If set to 1mm, a difference below -1 will show all red and above 1 will show all blue.
Please see
Simulation (Fast Version)
for information about how Stock Compare is used in the simulation window.
Please note that the Cross Section View, which is a feature in the Geometry Manager tab, also has an option to compare the stock and workpiece. Please see the
Geometry Manager
tab for more information.
Stock Compare is only available for Fast version simulation.
Zoom Window
Select this option to increase the accuracy of the stock within the simulation window. This option creates a cut out of the stock that covers the window.
Use the
Reset Zoom
option to show the entire stock.
Only available for Fast version simulation.
Zoom Selection
Select this option to increase the accuracy of the stock within a user-defined area.
Select this option
In the simulation window, click and hold the left mouse button
Drag out a rectangle.
Release the mouse to make the cut out.
Use the
Reset Zoom
option to show the entire stock.
Only available for Fast version simulation.
Reset Zoom
Select this option to reset the simulation window when using
Zoom Window
or
Zoom Selection
.
Only available for Fast version simulation.
Cross Section
Click this option to turn the cross section view on or off.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/tool/
TITLE: Tool
======================================================================
PDF
Program Tabs
Backplot
Tool
Tool
This section describes the options in the
Tool
menu which are used for configuring and visualizing tools in the simulation.
Tool menu.
Menu options
Show/Hide Tool
Select this item to show or hide the simulation tool.
Click the down arrow to access a variety of tool display options.
Show Tool Holder
Select this item to show the toolholder.
Show Tool Transparent
Select this item to show the tool transparent.
Show Tool Colors
Select this item to show the tool colors.
Show Tool Vector
Select this item to show the tool vector.
Show All Tools
If multiple tools are used in the program, each one will be visible throughout the simulation.
Tool 1-N
Show/hide individual tools in the simulation.
Tool Setup (Tool Manager)
Click this icon to open the Tool Manager. View and modify the tools in your NC program, configure tool types, colors,and more. Please refer to
Tool Manager
for further information.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/toolpath/
TITLE: Toolpath
======================================================================
PDF
Program Tabs
Backplot
Toolpath
Toolpath
This section describes the options in the
Toolpath
menu which are used for controlling and visualizing the simulation of toolpaths.
Toolpath menu.
Menu options
Toolpath
Select this option to toggle the visibility of toolpaths.
Click the down arrow to access a variety of toolpath display options.
Toolpath options.
Hide Toolpath
Hides the entire toolpath.
Show Points
Shows the individual points that make up the toolpath.
Show Rapid Moves
Shows the rapid, non-cutting movements of the tool.
Show Cutting Moves
Shows the actual cutting movements of the tool.
Highlight Arcs
Highlights arc movements in the toolpath.
Highlight Element
Highlights the current elements of the toolpath simulation.
Large Points
Enlarges the points on the toolpath for better visibility and differentiation from other elements.
Mode
Show toolpath from start until current position.
Click on the down arrow to open a drop-down menu, from which you can select options and additional functions for toolpath simulation.
Options for toolpath simulation.
Animate / Show From start
Begins the simulation by only displaying the initial segment of the toolpath. Subsequent toolpaths become visible progressively as the machining process unfolds.
Animate / Show Remaining Toolpath Dimmed
Runs the simulation while dimming the unprocessed part of the toolpath.
Animate / Show To End
Begins the simulation by displaying all toolpaths and then gradually hides the completed sections of the toolpath.
Animate / Show Entire Z-Level
Shows all toolpaths at the current Z-level.
Animate / Show Current Z-Level
Shows the current toolpath at the current Z-level.
Animate / Show Tail
Shows only a part of the toolpath following the tool.
Animate / Show From Last Rapid
At any point in the simulation, this option hides the toolpaths preceding the previous rapid move.
Animate / Show From Last Tool Change
At any point in the simulation, this option hides the toolpaths preceding the previous tool change.
Animate / Show Current Navigation
This option shows all moves in the current navigation group.
Animate / Show Active Plane
This option shows all moves in the current active plane.
Animate Tool Only
Shows the entire toolpath while only animating the tool.
Remember Animation Mode Between Sessions
Select this option to remember the animation
Mode
after closing Backplot and starting it again. Otherwise it will reset to its default.
Track Tool
Follows the tool and ensures the simulation maintains the tool's position at a fixed point on the screen.
Loop Simulation
Repeats the simulation until stopped by the user.
Stop Conditions
Select this option to toggle Stop Conditions which force the simulation to stop when specific events occur.
Click the down arrow to select which events should stop the simulation. See options below.
Stop Condition options.
See
Simulation (Fast Version)
for information about the Stop Conditions panel in the Simulation Window.
The Stop Conditions option is only available for
Machine Simulation
.
Tool Change
Enable this to stop the simulation upon detecting a tool change.
Collision
Enable this to stop the simulation upon detecting a collision.
Rapid To Stock
Enable this to stop the simulation upon detecting a rapid movement that collides with the stock.
Stopped Spindle Cuts
Enable this to stop the simulation upon detecting the tool cutting while the spindle is stopped.
Holder To Stock
Enable this to stop the simulation upon detecting a collision between the tool holder and stock.
Tool And Models
Enable this to stop the simulation upon detecting a collision between the tool and any model in the simulation such as workpiece, fixture or machine models.
Travel Limits
Enable this to stop the simulation upon detecting that an axis has exceeded its travel limit.
Optional
Enable this to stop the simulation upon detecting a stop command in the NC program.
M00: Program Stop
M01: Optional Stop
M02: End of Program
M30: Program End and Reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/view/
TITLE: View
======================================================================
PDF
Program Tabs
Backplot
View
View
This section describes the options in the
View
menu which are used for navigating and visualizing the simulation.
View menu.
Zoom in and out with the mouse wheel.
Menu options
Fit To Window /
F9
Click this option to adjust the view to show all elements while maintaining the current perspective. A click with the middle mouse button in the Backplot window does the same.
Zoom Selection
Click this option to zoom in on a selected area. After selecting the option, click and hold the mouse button to draw a box around the region you want to magnify.
Zoom To Highlighted
Click this option to zoom in on the currently highlighted (active) element in the simulation.
To see the highlighted element, enable the
Highlight Element
option under
Toolpath
. Click the down arrow to show the options.
Once enabled, the simulation will highlight each toolpath element sequentially as it runs the program.
View Reset
Click this option to reset the view to the initial size and position.
View from Tool
Click this icon to view the simulation from the tool.
View from Top (XY/G17)
Click this icon to view the simulation from the top.
View from Bottom (XY)
Click this icon to view the simulation from the bottom.
View from Front (XZ/G18)
Click this icon to view the simulation from the front.
View from Back (XZ)
Click on this icon to view the simulation from the back.
View from Left (YZ/G19)
Click on this icon to view the simulation from the left.
View from Right (YZ)
Click this icon to view the simulation from the right.
Rotate View
Select this option to enable view rotation by clicking and holding the left mouse button.
Zoom View
Select this option to enable view zoom by clicking and holding the left mouse button. Move the mouse up to zoom in and down to zoom out.
Pan View
Select this option to enable view panning by clicking and holding the left mouse button.
Measure Distance
Click this option to measure the distance between two points in the simulation.
The measurement tool supports snapping to geometry, edges, and corners, making it easier to select precise measurement points.
Fast Version
When enabled, a dedicated measurement panel will appear on the left side of the simulation window with details of your measurement.
To carry out a measurement:
Click on the starting point for the measurement within the simulation.
Click on the endpoint you wish to measure towards.
To conduct another measurement, simply repeat the process.
After a distance has been measured, you can navigate the view (rotate, zoom, etc.) without the measurement arrow being removed.
See
Simulation (Fast Version)
for more information about the panel.
Standard Version
In the
Standard version
you can see the details of your measurement in the
Information Bar
at the bottom of the simulation window.
Click the starting point for the measurement within the simulation.
Move the cursor to the endpoint you wish to measure towards (do not click).
See your measurement data in the
Information Bar
.
To conduct another measurement, simply repeat the process.
In Standard version, a click will always restart the measurement.
See
Simulation (Standard Version)
for more information about the panel.
Show Bounding Box
Select this option to show the toolpath bounding box.
Show Machine Origin
Select this option to show the machine origin.
Show Toolpath Origin
Select this option to show the toolpath origin.
Show Plot Control
Select this option to show/hide the plot control.
Projection View
Select this option to render the simulation while preserving the relative size of geometries. This makes it easier to compare the geometries at different depths.
Perspective View
Select this option to render the simulation using a camera position and a field of view. The camera can move through geometries for better inspection of fine details. However, geometries far away appears smaller on the screen, making it harder to compare the relative size of objects.
Show Axis Control
Axis Control allows you to track the position of each axis during the simulation. Any axis that runs over its travel limit is highlighted in red.
Scroll the mouse wheel on each Axis Control Bar to zoom in and out which allows you to make fine adjustments and see it update in real time.
The Axis Control panel is located at the upper-right corner of the simulation window. See
Simulation (Fast Version)
for more information.
Show Plot Control
Click the down arrow of
Show Axis Control
and select this option to show the backplot control bar.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/
TITLE: Simulation
======================================================================
PDF
Simulation
Simulation
CIMCO Edit 2026 includes two simulation engines; the
Standard version
and the new
Fast version
which is now the default engine. You can change the version in the
Backplot configuration
section in the Editor Setup.
Also, before starting the simulation, you first need to configure backplot for the
File type
of the program you wish to simulate. Open the
Backplot configuration
dialog in the Editor Setup, select the
Control Type
(for example 'ISO Milling') and configure the desired parameters. See
Backplot configuration
for more information.
Overview of the Backplot tab and simulation window.
Ribbon bar menu (Backplot)
:
Easy access to relevant simulation options
NC program view (left):
Shows your NC program in sync with the simulation
Simulation window (center):
Shows the actual 3D simulation and controls (using
Fast version
or
Standard version
)
Docking pane (right):
Contains multiple tabs, including:
Simulation
:
Simulation Report and settings
Navigation
:
Overview of NC program
Variables
:
Tracking of variables in your NC code during simulation.
Geometry Manager
:
Setup of elements in the simulation
Subsections
Simulation (Fast Version)
Simulation (Standard Version)
Simulation Tab
Navigation Tab
Variables Tab
Geometry Manager Tab
Tool Manager
Machine Simulation
Presentation Viewer
Supported Controls
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/fast-version/
TITLE: Simulation Window (Fast Version)
======================================================================
PDF
Simulation
Simulation (Fast Version)
Simulation Window (Fast Version)
This section describes the Simulation Window and its user interface elements when using Fast version simulation.
Fast Version simulation window.
Navigate 3D View (Rotate, Zoom and Pan)
Rotate View:
Click and hold the left mouse button over the simulation window, then drag to rotate the view around a point of interest.
Zoom:
Use the scroll wheel to zoom in for a closer look or out to see more of the simulation.
Pan:
To shift your view without changing the orientation, click and hold the right mouse button and move the mouse to pan across the simulation space.
Playback Controls
Progress Bar
The Progress Bar shows the current position in the NC program. Click and drag the blue handle to move the simulation forward or backwards.
Use the mouse scroll wheel to zoom in and out on the Progress Bar for more precise positioning of the slider.
Direction and Speed Slider
When the simulation is started, use this slider to set the direction and speed of playback.
Forward:
from midpoint to the right (slow to fast)
Backward:
from midpoint to the left (slow to fast)
You can adjust the slider by either dragging it or using the scroll wheel on your mouse.
Start / Stop simulation
Select this to start the simulation. Use
Ctrl + Shift + R
to play or pause the simulation.
Pause simulation
Select this to pause the simulation.
Jump to next move
Select this to jump to the next move. Use the corresponding option to jump to the previous move.
Jump to next Z-level
Select this to jump to the next Z-level. Use the corresponding option to jump to the previous Z-level.
Jump to next cutting pass
Select this to jump to the next cutting pass. Use the corresponding option to jump to the previous cutting pass.
Jump to next tool
Select this to jump to the next tool change. Use the corresponding option to jump to the previous tool change.
Jump to end of program
Select this to jump to the end of the simulation. Use the corresponding option to jump to the beginning of the simulation.
You can also press
Ctrl + Shift + Space
to jump to the end of the simulation.
Panels
Tool Position and Status Panel
The Tool Position and Status Panel is located at the upper-left corner of the screen, providing easy access to monitor your tool's current position and status.
The upper section of the panel shows the current tool's position on each of the available axes such as along X, Y, Z, A, B, and C. The availability of these axes varies depending on machine configuration.
In the lower section under
Status
, the following parameters are shown:
Tool:
The current tool number
Feed:
The current feed. Simply displays
Rapid
for rapid moves.
Spindle speed:
The current spindle speed in revolutions per minute (RPM).
Dist:
Shows the current toolpath distance that tool(s) have traveled during the program/simulation.
Total:
Shows the total distance of all toolpaths within the program.
The units used for some of these parameters can be configured for individual machine controls in the
Machine
section in the Editor Setup.
Stock Compare Panels
The
Stock Compare
option is used to compare the stock to a design model (Workpiece). The stock is color-coded based on its distance to the design model to easily identify any inaccuracies, whether too much stock has been removed (the tool gauges the design model) or where not enough stock has been removed.
Compare Visibility
This panel contains three buttons and two options:
Less:
Toggle red color which indicates areas with too little material left.
Range:
Toggle green color which indicates the stock is within tolerance
Greater:
Toggle blue color which indicates areas with too much material left.
Compare Range:
Refers to the tolerance range within which the stock is considered to be machined correctly. If set to 1mm, a difference below -1 will show all red and above 1 will show all blue. See Stock Compare under the
Solid
menu for further information.
Stock to leave:
The expected difference. For example, if you expect to leave 1mm of material for a later process, you can set this to 1. See Stock Compare under the
Solid
menu for further information.
Compare Range
Red color:
Indicates areas where the stock has been over-machined and too much material has been removed
Blue color:
Indicates areas where the stock has been under-machined and too little material has been removed
Green color:
Indicates the stock is within tolerance
Hover the mouse:
Hover the mouse over the colored stock to see the distance to the design model in different areas
Axis Control Panel
The Axis Control panel is located at the upper-right corner of the screen and allows you to track the position of each axis during the simulation. Any axis that runs over its travel limit is highlighted in red.
Scroll the mouse wheel on each Axis Control Bar to zoom in and out which allows you to make fine adjustments and see it update in real time.
The option to enable Access Control is located in the Backplot tab under the
View
menu.
Quality and True Vision
To show the
Quality and True Vision
panel, select the stock in the
Geometry Manager
.
Use the
Quality slider
to adjust the rendering precision of the selected stock. A higher setting provides greater accuracy but also increases processing time.
Enable the
True Vision checkbox
to activate advanced pixel-perfect rendering with even higher precision. This mode takes the exact tool profile and other key parameters into account for a more realistic simulation.
True Vision is only visible when the simulation window is stationary. It is temporarily disabled while rotating, panning, or zooming the simulation view.
Cross Section Plane Panel
This panel appears when
Cross Section View
is enabled which allows you to slice the stock along an axis. This is enabled in the
Geometry Manager
by right-clicking the stock and selecting
Cross Section
.
See
Geometry Manager
for more information.
X+
The position of the slice along the X axis. This will change to the axis currently being sliced.
Tool Plane:
Enable this to set the cross sections relative to the current active tool plane.
Workpiece:
Enable this to compare the stock with the workpiece. Red color indicates that too much material has been removed while yellow color indicates too little has been removed.
Stop Conditions Panel
When a
Stop Condition
is triggered, this panel appears on the right side of the screen with information about the cause of the stop. In this example the simulation has stopped because the Y-axis has traveled beyond its limit.
The Stop Conditions option is only available for
Machine Simulation
.
Measure Distance Panel
This panel appears on the left side when the Measure Distance option is enabled in the Backplot tab under the View menu. The
Measure Distance
option is used to measure the distance between 2 points.
Workpiece Position Panel
Shows the position of origin of the Workpiece. See the option
Select origin in simulation
in the
Geometry Manager
for more information.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/geometry-manager/
TITLE: Geometry Manager Tab
======================================================================
PDF
Simulation
Geometry Manager Tab
Geometry Manager Tab
This section describes the
Geometry Manager
tab which is located in the docking pane.
The Geometry Manger is used for setting up the simulation environment including origin, offsets, workpiece, fixture, machine models, and stock. It is divided into two areas: the upper section shows the elements within the simulation environment, while the lower section lists the properties of the selected element.
Right-click anywhere in the Geometry Manager or on a specific element to see the options available.
Geometry Manager tab.
Elements
Work Origin
Specify a position on the machine relative to the machine zero position using the Translation properties.
Properties:
Translation:
the X-Y-Z position of the origin
Work Offsets
Adjust Work Offsets using the properties below.
Properties:
Number:
the work offset number
Translation:
the X-Y-Z position
Rotation:
the A-B-C rotation
Collinear:
the U-V-W position of the collinear axes
Only the axes the machine has are shown.
If the NC program sets the work offset, for example with G10 L2 or a macro variable, the read-only rows
Programmed Translation
,
Programmed Rotation
and
Programmed Collinear
show the values the program has written at the selected position in the program.
Sub-Spindle Offset
Only shown when the machine has a sub-spindle. Use the
Translation
property to move the sub-spindle zero point from the position set in the machine configuration. The simulation uses this position when the program moves the sub-spindle.
Properties:
Translation:
the X-Y-Z offset
The Head, Table and Base elements below are only available for
Machine Simulation
.
Head
Shows the head of the machine and its associated axes. Right-click to set visibility. Can be modified using the
Machine Configuration Editor
Table
Shows the table of the machine and its associated axes. Right-click to set visibility. Can be modified using the
Machine Configuration Editor
Base
Shows the base of the machine and its associated axes. Right-click to set visibility. Can be modified using the
Machine Configuration Editor
Fixtures / Add Fixture
Shows the fixtures that have been added to the simulation environment. To add a fixture, right-click anywhere in the Geometry Manager and select the option
Add Fixture
. Locate the corresponding STL file and click
Open
. The fixture will appear below
Fixtures
.
Properties:
Translation:
the XYZ position
Rotation (Euler):
the Z-X-Z" rotation
Color:
the color defined in RGB (0-255)
Unit System:
changes the unit of measurement
Mount Axis:
Automatic or set to an axis.
Workpieces / Add Workpiece
Shows the workpieces that have been added to the simulation environment. To add a workpiece, right-click anywhere in the Geometry Manager and select the otion
Add Workpiece
. Locate the file and click
Open
. The workpiece will appear below
Workpieces
.
Properties:
Translation:
the XYZ position
Rotation (Euler):
the Z-X-Z" rotation
Color:
the color defined in RGB (0-255)
Unit System:
changes the unit of measurement
Stock / Add Stock (STL/DXF/Cylinder/Box)
Shows the stock that have been added to the simulation environment. You can only add one stock. Right-click in the Geometry Manager and select
Add Stock
.
You will see an additional menu with the following options:
STL:
Add an STL model as stock
DXF:
Add an DXF model as stock
Cylinder:
Add a cylinder shaped stock
Box (Dimensions, Min/Max):
Add a rectangular stock
You can also add a stock using the option in the Solid menu under the Backplot tab. See the
Solid
menu for detailed descriptions of the different types of stock.
Once added, the stock will appear in the Geometry Manager. Select the stock to configure its properties and to reveal the
True Vision panel
in the simulation window:
Properties (general):
Quality:
set the quality of the stock model. Higher is more precise, but requires more processing (slower)
Translation:
the X-Y-Z position
Properties (STL):
Rotation (Euler):
the Z-X-Z" rotation
Path:
the path to the .stl file (click the ... on the right, to select a file)
Unit System:
changes the unit of measurement
Properties (Cylinder):
Diameter:
the diameter of the stock
Height:
the height of the stock
Axis:
the axis that "points through" the cylinder
Origin:
set the position of the origin of the stock
Properties (Dimensions):
Height:
the height of the stock
Width:
the width of the stock
Length:
the length of the stock
Origin:
set the position of the origin of the stock
Properties (Min/Max):
Lower Corner:
X-Y-Z position
Upper Corner:
X-Y-Z position
Additional right-click options
Detect from machine definition
Right-click the
Work Origin
in the Geometry Manager and select this option to copy the XYZ position from the machine definition.
To see the machine definition and its properties, open the
Backplot
section in the Editor Setup and then click the button with the machine icon on the right side of the
Machine Setup (4/5-Axis)
dropdown. This will open the
Machine Configuration Editor
where you can select the
Base
and then see the
Default Origin
property.
Select origin in simulation
Right-click the
Work Origin
in the Geometry Manager and select this option to highlight the position of the Work Origin in the simulation. The position is indicated by a white point and the red/green/blue coordinate system axes.
Drag the axes to modify the position of the origin directly in the simulation window.
The XYZ position is displayed in the Workpiece position panel on the right side of the simulation window.
Visibility
Right-click an element and select
Visibility
to set it to Visible, Hidden, or Transparent.
Cross Section
Right-click the stock and select
Cross Section
to slice the stock along an axis. In the simulation view, drag the arrows of the coordinate system element to change the position of the slice.
When activated, the
Cross Section Plane Panel
will appear in the simulation window.
Select
OFF
to disable the Cross Section option.
This option is only available for Fast version simulation.
Remove
Right-click an element and select
Remove
to remove it (if possible).
Regenerate
Right-click the stock and select this option to regenerate (refresh) the solid model of the stock at the current position in the NC program.
This option is only available for Standard version simulation.
Save Setup
Right-click anywhere in the Geometry Manager and select
Save Setup
to save the entire setup.
By default a .setup file will be created in the same location as the NC program you are simulating. The setup file is automatically loaded when starting Backplot / simulation.
Both the loading and saving of the Geometry Manager setup, its elements and tool data are part of the
Scanning
configuration in CIMCO Edit. Please refer to the
Scanning
section in the Editor Setup for more information.
Save STL file
Right-click the stock in the Geometry Manager and select
Save STL file
to save the stock, as it is shown at the current position in the NC program / simulation, as an STL file.
Copy Position
Right-click an element and select this to copy its
Translation
and
Rotation
properties.
Paste Position
Right-click an element and select this to paste the
Translation
and
Rotation
properties previously copied.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/machine-simulation/
TITLE: Machine Simulation
======================================================================
PDF
Simulation
Machine Simulation
Machine Simulation
Machine Simulation is an add-on for CIMCO Edit 2026, but it is
not
a separate download you need to install. Machine Simulation is already installed as part of CIMCO Edit and its features simply become available once a valid license key has been installed.
Getting started
Machine Simulation is started from the
Machine Simulation
option in the
Backplot
menu. This is similar to starting Backplot except it shows the machine and provides some additional options in the simulation window and in the Simulation and Geometry Manager tabs (see below). However, to see a machine in the simulation you first need to follow a couple of steps.
Go to the
Machine Models
section in the Editor Setup and install the machine you want to simulate.
Under the Backplot menu tab, select the Control and Machine from the dropdown in the
Control Type
menu. Downloaded machines will show '(Bundled)' after their name.
Start Machine Simulation from the
Backplot
menu and you should now see the machine in the simulation and its components in the
Geometry Manager
tab.
Custom Machines
If the machine you want to simulate is not available, you can use the
Machine Configuration Editor
, located in the Editor Setup under
Custom Machines
, to configure your own.
You can also let CIMCO create it for you. We will then create the machine and email you a single .MacBundle file (Machine Bundle) that you can install. The installer simply unpacks the necessary files in the right location within CIMCO Edit and you can then start simulating with the machine.
Please
contact us
to learn more about this process.
Exclusive Features
The following outlines the features that become available with Machine Simulation.
Simulation Report and Settings
When Machine Simulation is started, the
Simulation Report
(located in the Simulation tab) will also include information about collisions and limit errors.
A section with Collision Settings will also be available in the Settings section of the
Simulation tab
.
Geometry Manager
When Machine Simulation is started, the
Geometry Manager
will show additional components for the current machine's Head, Table and Base. Expanding any of these will reveal the STL models used to visualize the machine's components.
You can use the visibility option to show or hide components.
Stop Conditions
The Stop Conditions option allows you to automatically stop the simulation when specific events occur. This could be a collision, tool change, stopped spindle, exceeded travel limit, etc. The Stop Conditions options can be found and enabled in the
Toolpath menu
under the Backplot tab.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/navigation/
TITLE: Navigation Tab
======================================================================
PDF
Simulation
Navigation Tab
Navigation Tab
This section describes the
Navigation
tab which is located in the docking pane.
During the simulation of an NC program, the Navigation tab offers a well-organized overview (a tree menu) of the program's contents. This feature facilitates quick and effortless pinpointing of corresponding positions in both the NC program and the Navigation tab.
To use Navigation, simply select a keyword in the tree menu to automatically jump to the corresponding keyword in the active NC program. Select any line in the NC program and the nearest keyword in the Navigation tree will be highlighted.
Right-click anywhere in the Navigation pane to either expand or collapse all levels in the tree menu.
Navigation tab.
Activation and Configuration
To activate Navigation, you must first enable the option 'Scan for navigation information' found within the
Scanning
dialog of the Editor Setup. Following that, configure the structure and keywords for scanning in the
Navigation
dialog, also located in the Editor Setup.
Please note that the Navigation tab is only visible and updated while simulation (Backplot) is active.
Please refer to the
Navigation
dialog for information on how to configure the structure and keywords.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/presentation-viewer/
TITLE: Presentation Viewer (Stand-alone simulation)
======================================================================
PDF
Simulation
Presentation Viewer
Presentation Viewer (Stand-alone simulation)
The Presentation Viewer allows you to export and share complete simulations from CIMCO Edit for viewing as stand-alone presentations, without requiring CIMCO Edit to be installed. Using the
Save Presentation
option, an entire simulation can be saved and viewed in a dedicated viewer application, making it easy to share simulation results with colleagues, customers, or support.
Presentations can be saved either as a simulation file containing only the simulation data, or as a complete presentation bundle that also includes the viewer application. Simulation bundles automatically include any external subprograms used by the simulation, ensuring they are available when the presentation is opened on another computer.
The viewer application only needs to be installed once and can then be used to view multiple simulations exported from CIMCO Edit. Simulation files are compact and well suited for archiving alongside related NC documentation such as setup sheets and tool lists, and for easy distribution.
All options and panels described here exist in CIMCO Edit and are also available in the Presentation Viewer.
Application window
The overall application window is divided into five primary areas:
Ribbon / Toolbar (Top)
3D Simulation Viewport (Center)
Information Panels (Left)
Axis Control Panel (Right)
Playback & Timeline Controls (Bottom)
Presentation Viewer application.
Ribbon / Toolbar (Top
The ribbon bar provides access to all simulation, visualization, and verification tools. Icons are grouped logically and can be enabled or disabled independently.
Tool
Displays the active tool assembly (cutter + holder).
Workpiece
Defines and displays the raw stock geometry.
Fixture
Displays fixtures such as vises, clamps, tombstones, or custom fixturing.
Stock
Controls visibility and visualization of the stock model.
Quality
Opens a side panel that controls surface quality visualization, allowing the user to adjust the quality level from low to high and enable or disable True Vision for a more realistic surface appearance.
Zoom Window
Allows box-zooming into a selected area of the viewport.
Compare
Enables stock comparison view, allowing the current stock state to be compared against a reference stock using color mapping and tolerance settings, equivalent to the Stock Compare option in CIMCO Edit.
Cross Section
Enables the cross-section view, displaying a movable section plane that allows the stock, tool, and workpiece to be dynamically cut and inspected using adjustable plane position and orientation.
Toolpath
Opens the toolpath visualization menu, allowing the toolpath to be shown or hidden and providing multiple visualization and animation modes.
Stop Conditions
Defines simulation stop rules (tool change, block, collision).
Collision Checking
Opens the collision checking panel, enabling real-time detection of collisions between tool, holder, workpiece, stock, and machine components, with configurable checking options and a detailed, time-stamped collision event list.
View
Standard camera views (Top, Front, Isometric, etc.).
Measure Distance
Measures distances directly in the 3D scene.
Show / Hide Controls
Toggles UI overlays.
Machine Simulation
Enables full machine kinematics.
Show / Hide Head
Toggles visibility of the spindle / head.
Show / Hide Table
Toggles visibility of the machine table.
Show / Hide Base
Toggles visibility of the machine base/frame.
3D Simulation Viewport
The central viewport displays the real-time simulation, showing material removal, tool and holder motion, machine axis movement (X, Y, Z, A/B/C), collision visualization, stock colorization, and cross-section inspection, with interactive mouse orbit, pan, and zoom controls, zoom window selection, and continuous live updates during playback.
Tool Position and Status Panel
Displays the current tool position for linear (X, Y, Z) and optional rotary axes (A, B, C) with units in millimeters and degrees, updating continuously during simulation playback, while also showing machining status information such as active tool number, feedrate, spindle speed, elapsed time, and total machining time for cycle-time validation and presentation overview.
NC Program Panel
Displays the NC program lines, highlighting the currently executed block and scrolling automatically during playback, making it suitable for code walkthroughs, debugging, training, and presentation purposes.
Axis Control Panel
Provides manual axis positioning using sliders and numeric readouts for X, Y, Z, and optional rotary axes (A/B/C), allowing manual inspection, collision checking, demonstration of machine reach, and positioning independent of program execution.
Playback & Timeline Controls
Controls simulation execution using play and pause, step forward and backward, fast forward and rewind, start and end navigation, adjustable playback speed, and a timeline scrubber, with identical behavior in CIMCO Edit Simulation and the Presentation Viewer.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/simulation/
TITLE: Simulation Tab
======================================================================
PDF
Simulation
Simulation Tab
Simulation Tab
This section describes the
Simulation
tab which is located in the docking pane. The tab is divided into two main areas: the upper section displays the Simulation Report, while the lower section is dedicated to various simulation settings.
Simulation Report
The Simulation Report lists all program errors that have been detected within the NC program, including the line number the error occurs on, the type of error, a description of the error and the action taken. The Simulation Report also provides information about collisions and limits when the
Machine Simulation
add-on is being used.
The
ACTION
column describes what action CIMCO Edit will take until the error is resolved such as ignoring a command or highlighting a collision.
Click on any program error in the list to jump to the corresponding line and highlight the error in the NC program.
The Simulation Report automatically updates when changes are made to the NC program and errors are immediately removed from the list when corrected.
Error checking can be disabled under Simulation Settings / Report errors (see below).
Simulation Report in upper section of Simulation tab.
Check collision and limit errors
Click this button to rerun collision detection. This task can be CPU intensive, particularly for large programs, so it does not run with each modification to the NC code. Using this button, you can decide when to execute the collision detection.
This option is only available for
Machine Simulation
.
Show Errors
Enable this option to show error messages in the Simulation Report.
Show Warnings
Enable this option to show warnings in the Simulation Report.
Settings
Collision Settings
The collision settings only show when
Machine Simulation
is enabled.
Collision checking per model
This function defines whether collision checking should stop after finding the first collision (Find One) or continue to find all possible collisions (Find All) between pairs of machine components. The term "per model" can be a bit misleading, as it actually means "per model pair" – i.e., collisions between two specific components.
Find One:
Detects one collision for each type of model pair (e.g., tool/workpiece or C-axis/Z-axis).
Find All:
Detects all collisions for all model pairs. This can potentially be slow.
Tool/Workpiece Collisions
This option controls collision detection between the tool and the workpiece and offers the following settings:
ON:
Detects all collisions between the tool and the workpiece.
Rapid Moves:
Only detects collisions during rapid (non-cutting) moves.
Cutting Moves:
Only detects collisions during cutting operations.
OFF:
Disables all collision detection between the tool and the workpiece.
It can be useful to turn this off because the tool frequently comes into contact with the workpiece during normal machining, which can slow down collision detection. Additionally, this type of collision can often be handled more effectively using
Stock Compare
instead.
Collision Step Size
This option defines the distance between points along the toolpath where collision checks are performed.
Since the simulation cannot check for collisions continuously, it places multiple points along the toolpath and checks for collisions at each one. A smaller step size increases accuracy but may slow down processing, while a larger step size speeds up simulation but might miss some collisions.
Cutter Allowance
This option defines how far the cutter can penetrate the workpiece before a collision is reported.
Since STL models are made up of triangles with a small margin of error, the cutter may appear to touch the workpiece slightly, leading to false positive collision detections. By setting a value (e.g., 0.1mm), you allow the cutter to move that distance into the workpiece before it is considered a collision. This helps reduce unnecessary collision warnings caused by minor inaccuracies in the model.
Hidden model collisions
This option controls whether collisions involving hidden models should be detected and reported.
ON:
Collisions are checked even for hidden models. This ensures all collisions are detected.
OFF:
Collisions for hidden models are ignored. This prevents unnecessary collision reports for models that are hidden.
If a model is hidden only for better visibility but still important for collision detection, this option should remain enabled.
Stock Verification Settings
Refine edges
Enable this to improve the precision of edges in the stock model.
Yes:
Enabled
No:
Disabled
This option is not available when the new enhancing algorithm is enabled.
Rapid collisions
Enable this to check for collisions during rapid movement.
On (Highlighted in red):
Enabled
Off:
Disabled
Stopped spindle
This option determines what should happen in the simulation when the spindle is not turning (spindle speed is 0).
Cut:
Ignore the error and cut the stock material anyway.
No cut:
Do not cut the stock material.
Mark collision:
Cut the stock material, but mark the cut red.
Tool colors
Enable this to add a distinct color to the machined areas of the stock, corresponding to each tool used.
On:
Enabled
Off:
Disabled
Quality zoom depth filter
Enable this to limit the options
Zoom window
and
Zoom selection
(in the
Solid
menu) to only make a "cut out" to a certain depth in the view direction.
On:
Enabled
Off:
Disabled
Simulation Settings
Maximum Loop Iteration Limit
If a loop is encountered within the NC program being simulated, this setting controls how many loop iterations will be allowed before CIMCO Edit triggers the
Behavior When Limit is Reached
action (below).
Behavior When Limit is Reached
This setting controls what will occur when the
Maximum Loop Iteration Limit
(above) is reached.
Ignore the limit
Break out of the loop
Prompt for decision
Radius compensation
This setting controls whether radius compensation is ignored or not.
Enabled:
Radius compensation is not ignored
Disabled:
Radius compensation is ignored
Arc Type
Controls how to interpret the arc center specification.
As in G-code
: the arc is interpreted as it is written in the G-code and control settings.
Auto-detect
: the system will automatically detect whether the arc moves are absolute or incremental based on a geometrical interpretation.
Relative to start
: the arc type is forced to be incremental.
Absolute arc center
: the arc type is forced to be absolute.
Radius value
: the arc is interpreted using a radius value.
Subprogram folder
When simulating an NC program that includes subprograms, CIMCO Edit automatically searches for the subprogram files in the same directory as the main program file. However, if you need to, you can use this option to specify a different folder to search for subprogram files.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/standard-version/
TITLE: Simulation Window (Standard Version)
======================================================================
PDF
Simulation
Simulation (Standard Version)
Simulation Window (Standard Version)
This section describes the
Simulation Window
and its user interface elements when using Standard version simulation.
Standard version simulation window.
Navigate 3D View (Rotate, Zoom and Pan)
Rotate View:
Click and hold the left mouse button over the simulation window, then drag to rotate the view around a point of interest.
Zoom:
Use the scroll wheel to zoom in for a closer look or out to see more of the simulation.
Pan:
To shift your view without changing the orientation, click and hold the right mouse button and move the mouse to pan across the simulation space.
Playback Controls
The
Information Bar
, located at the bottom of the simulation window, contains different controls to navigate the simulation and shows tool information based on the current position in the NC program.
Information Bar.
Progress Bar (0 - 100%)
The Progress Bar shows the current position in the NC program. Click and drag the blue handle to move the simulation forward or backwards.
Speed and Direction Slider
When the simulation is started, use this slider to set the direction and speed of playback.
Forward:
from midpoint to the right (slow to fast)
Backward:
from midpoint to the left (slow to fast)
Start / Stop simulation
Select this to start the simulation.
Pause simulation
Select this to pause the simulation.
Jump to next move
Select this to jump to the next move. Will jump to previous when
Speed and Direction Slider
is in reverse.
Jump to next cutting pass
Select this to jump to the next cutting pass. Will jump to previous when
Speed and Direction Slider
is in reverse.
Jump to next Z-level
Select this to jump to the next Z-level. Will jump to previous when
Speed and Direction Slider
is in reverse.
This option is not available when simulating a turning program.
Jump to next tool
Select this to jump to the next tool change. Will jump to previous when
Speed and Direction Slider
is in reverse.
Show / hide information bar
Select this to toggle the visibility of the Information Bar.
Tool Data and Measurement
Tool Position and Status
The data fields display the tool data relevant to the current position within the simulated NC program. The fields presented will vary depending on whether the program is designed for milling or turning operations.
Measure Distance
These data fields appears when the Measure Distance option is enabled in the Backplot tab under the View menu. The
Measure Distance
option is used to measure the distance between 2 points.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/
TITLE: Supported Controls
======================================================================
PDF
Simulation
Supported Controls
Supported Controls
Subsections
Brother
Centroid
Delectron
Fagor
Fanuc
Fidia
Flexium
Haas
Heidenhain
Hurco
Mazak
Mitsubishi
NumeriPath
OSAI
Okuma
Roeders
Siemens
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/brother/
TITLE: Brother
======================================================================
PDF
Simulation
Supported Controls
Brother
Brother
Subsections
Brother Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/brother/brother-milling/
TITLE: Brother Milling
======================================================================
PDF
Simulation
Supported Controls
Brother
Brother Milling
Brother Milling
List of G and M-codes for Brother Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G5_1
AI contour control / Nano smoothing / Smooth interpolation
G10
Programmable data input
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Input in inch
G21
Input in mm
G28
Automatic return to reference position
G30
2nd, 3rd and 4th reference position return
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G43
Tool length compensation +
G43_4
Tool center point control (type 1)
G43_5
Tool center point control (type 2)
G44
Tool length compensation -
G49
Tool length compensation cancel
G52
Local coordinate system setting
G53
Machine coordinate system setting
G53_1
Tool-axis direction control
G54
Workpiece coordinate system #1
G54_1
Additional workpiece coordinate systems
G54_2
Rotary fixture offset
G55
Workpiece coordinate system #2
G56
Workpiece coordinate system #3
G57
Workpiece coordinate system #4
G58
Workpiece coordinate system #5
G59
Workpiece coordinate system #6
G65
Subprogram call with arguments
G68
3-dimensional coordinate system conversion
G68_2
Tilted working plane command
G69
3-D coordinate conversion OFF
G73
High-Speed Peck Drilling Cycle
G74
Left-Handed Tapping Cycle
G76
Fine Boring Cycle
G77
Canned cycle tapping cycle (synchro mode)
G78
Canned cycle (Reverse tapping cycle) (synchro mode)
G80
Canned cycle cancel, Electronic gear box : synchronization cancellation
G81
Drilling Cycle, Spot Drilling
G82
Drilling Cycle, Counter Boring Cycle
G83
Peck Drilling Cycle
G84
Tapping cycle
G85
Boring cycle 1
G86
Boring cycle 2
G87
Boring cycle 2
G88
Boring cycle 3
G89
Boring cycle 4
G90
Absolute programming
G91
Incremental programming
G92
Work Coordinate Systems Shift Value
G92_1
Workpiece Coordinate System Preset
G94
Feed per minute
G95
Feed per revolution
G98
Canned cycle : return to initial level
G99
Canned cycle : return to R point level
G100
Non-stop automatic tool change
G102
XZ Circular interpolation CW
G103
XZ Circular interpolation CCW
G202
YZ Circular interpolation CW
G203
YZ Circular interpolation CCW
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M8
Coolant ON – Flood coolant
M9
Coolant Off
M30
End of program and reset
M98
Subprogram call
M99
Subprogram end
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/centroid/
TITLE: Centroid
======================================================================
PDF
Simulation
Supported Controls
Centroid
Centroid
Subsections
Centroid Milling
Centroid Turning
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/centroid/centroid-milling/
TITLE: Centroid Milling
======================================================================
PDF
Simulation
Supported Controls
Centroid
Centroid Milling
Centroid Milling
List of G and M-codes for Centroid Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G10
Parameter Setting
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Input in inch
G21
Input in mm
G28
Automatic return to reference position
G30
2nd, 3rd and 4th reference position return
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G43
Tool length compensation +
G43_3
Tool Length Compensation (+) with Axis Tilt Compensation
G43_4
Rotary Tool Center Point (with G43.3) Compensation
G44
Tool length compensation -
G49
Tool length compensation cancel
G52
Local coordinate system setting
G53
Machine coordinate system setting
G54
Workpiece coordinate system #1
G55
Workpiece coordinate system #2
G56
Workpiece coordinate system #3
G57
Workpiece coordinate system #4
G58
Workpiece coordinate system #5
G59
Workpiece coordinate system #6
G65
Subprogram call with arguments
G68
3-dimensional coordinate system conversion
G68_1
3-dimensional coordinate system conversion
G69
3-D coordinate conversion OFF
G73
High–Speed Peck Drilling Cycle
G74
Left–Handed Tapping Cycle
G76
Fine Boring Cycle
G80
Canned cycle cancel, Electronic gear box : synchronization cancellation
G81
Drilling Cycle, Spot Drilling
G82
Drilling Cycle, Counter Boring Cycle
G83
Peck Drilling Cycle
G84
Tapping cycle
G85
Boring cycle 1
G89
Boring cycle 4
G90
Absolute programming
G91
Incremental programming
G92
Work Coordinate Systems Shift Value
G94
Feed per minute
G95
Feed per revolution
G98
Canned cycle : return to initial level
G99
Canned cycle : return to R point level
G117
Rotation of Plane Selection XY
G118
Rotation of Plane Selection ZX
G119
Rotation of Plane Selection YZ
G173
Compound High Speed Peck Drilling
G174
Compound Counter Tapping
G176
Compound Fine Bore Cycle
G180
Compound Canned Cycle Cancel
G181
Compound Drilling and Spot Drilling
G182
Compound Drill with Dwell
G183
Compound Deep Hole Drilling
G184
Compound Tapping
G185
Compound Boring
G189
Compound Boring with Dwell
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M7
Coolant ON – Mist coolant/Coolant thru spindle
M8
Coolant ON – Flood coolant
M9
Coolant Off
M25
Move to Z Home
M30
End of program and reset
M98
Subprogram call
M99
Subprogram end
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/centroid/centroid-turning/
TITLE: Centroid Turning
======================================================================
PDF
Simulation
Supported Controls
Centroid
Centroid Turning
Centroid Turning
List of G and M-codes for Centroid Turning as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G10
Parameter Setting
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Input in inch
G21
Input in mm
G28
Automatic return to reference position
G30
2nd, 3rd and 4th reference position return
G32
Constant Lead Thread Cutting
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G52
Offset Local Coordinate System
G53
Rapid Positioning in Machine Coordinates
G54
Workpiece coordinate system #1
G55
Workpiece coordinate system #2
G56
Workpiece coordinate system #3
G57
Workpiece coordinate system #4
G58
Workpiece coordinate system #5
G59
Workpiece coordinate system #6
G65
Subprogram call with arguments
G70
Profile Finishing Cycle
G71
Profile Stock Removal in Turning
G72
Profile Stock Removal in Facing
G73
Profile Path Repeating Cycle
G74
End Face Peck Cutting Cycle
G75
Outside/Inside Diameter Peck Cutting Cycle
G76
Multi-pass Threading Cycle
G80
Canned cycle cancel, Electronic gear box : synchronization cancellation
G83
Peck Drilling Cycle
G84
Tapping cycle
G85
Boring cycle 1
G90
Outside/Inside Diameter Cutting Cycle
G92
Thread Cutting Cycle
G96
Turns on constant surface speed
G97
Cancels constant surface speed
G98
Feed per minute
G99
Feed per revolution
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M7
Coolant ON – Mist coolant/Coolant thru spindle
M8
Coolant ON – Flood coolant
M9
Coolant Off
M30
End of program and reset
M98
Subprogram call
M99
Subprogram end
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/delectron/
TITLE: Delectron
======================================================================
PDF
Simulation
Supported Controls
Delectron
Delectron
Subsections
Delectron Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/delectron/delectron-milling/
TITLE: Delectron Milling
======================================================================
PDF
Simulation
Supported Controls
Delectron
Delectron Milling
Delectron Milling
List of G and M-codes for Delectron Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G25
Contouring plane selection
G26
Subprogram end
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G43
Tool length compensation +
G44
Tool length compensation -
G45
Suspend tool length compensation
G53
Suspend the corrections introduced by supplementary origins and tool length
G54
Restoring of corrections due to supplementary origins and tool length
G55
Cancel mirroring on the working plane
G56
Enable mirroring on the working plane
G90
Absolute programming
G91
Incremental programming
G94
Feed per minute
G95
Feed per revolution
G116
Roto-translate a machining
G117
Rotating tool center point
G118
RTCP for rotary/tilting tables
G800
Canned cycles
G801
Positioning macros
G802
Machining macros
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M8
Coolant ON – Flood coolant
M9
Coolant Off
M19
Spindle orientation
M30
End of program and reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/fagor/
TITLE: Fagor
======================================================================
PDF
Simulation
Supported Controls
Fagor
Fagor
Subsections
Fagor Milling
Fagor Turning
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/fagor/fagor-milling/
TITLE: Fagor Milling
======================================================================
PDF
Simulation
Supported Controls
Fagor
Fagor Milling
Fagor Milling
List of G and M-codes for Fagor Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid Motion Positioning
G1
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G4
Dwell
G5
Controlled corner rounding (modal)
G6
Arc center in absolute coordinates (no-modal)
G7
Square corner (modal)
G8
Arc tangent to previous path
G9
Arc defined by three points
G10
Mirror image cancellation
G11
Mirror image on the first axis of the channel
G12
Mirror image on the second axis of the channel
G13
Mirror image on the third axis of the channel
G14
Mirror image in the programmed directions
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Main plane by two directions and longitudinal axis
G30
Polar origin preset
G31
Temporary polar origin shift to the center of arc
G36
Corner rounding, radius blend
G37
Tangential entry
G38
Tangential exit
G39
Corner chamfering
G40
Tool nose compensation cancel
G41
Tool Nose Compensation (TNC) Left
G42
Tool Nose Compensation (TNC) Right
G51
Smoothing Mode On
G53
Zero offset cancellation
G54
Select Work Coordinate System #1
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G60
Square corner (no-modal)
G61
Controlled corner rounding (no-modal)
G63
Rigid tapping
G70
Select Inches
G71
Select Metric
G72
Scaling factor
G73
Pattern rotation
G74
Machine reference zero (home) search
G80
Canned Cycle Cancel
G81
Drilling canned cycle
G82
Drilling canned cycle with variable peck
G83
Deep-hole drilling canned cycle with constant peck
G84
Tapping cycle
G85
Reaming canned cycle
G86
Boring canned cycle
G87
Rectangular pocket canned cycle
G88
Circular pocket canned cycle
G90
Absolute programming
G91
Incremental programming
G92
Set Local Work Coordinate System
G93
Machining time in seconds
G94
Feed Per Minute Mode
G95
Feed Per Revolution
G96
Constant surface speed
G97
Constant turning speed
G98
Canned cycle : return to initial level
G99
Canned cycle : return to R point level
G151
Programming in diameters
G152
Programming in radius
G158
Incremental zero offset
G159
Additional absolute zero offsets
G160
Multiple machining in straight line
G161
Multiple machining in rectangular pattern
G162
Multiple machining in grid pattern
G163
Multiple machining in a full circle
G164
Multiple machining in arc pattern
G165
Multiple machining in a chord pattern
G192
Programming the turning speed limit
G210
Bore milling canned cycle
G211
Inside thread milling cycle
G212
Outside thread milling cycle
G261
Arc center in absolute coordinates (modal)
G262
Arc center referred to starting point
G263
Arc radius programming
G501
Activates HSC on, defaulting to Surface mode (recommended) and allowing parameter overrides
M-Codes
Description
M0
Programmed stop
M1
Conditional program stop
M2
End of program
M3
Start the spindle clockwise
M4
Start the spindle counterclockwise
M5
Stop the spindle
M6
Tool change
M17
End of a global or local subroutine
M29
End of a global or local subroutine
M30
End of program and reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/fagor/fagor-turning/
TITLE: Fagor Turning
======================================================================
PDF
Simulation
Supported Controls
Fagor
Fagor Turning
Fagor Turning
List of G and M-codes for Fagor Turning as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid Motion Positioning
G1
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G4
Dwell
G5
Controlled corner rounding (modal)
G6
Arc center in absolute coordinates (no-modal)
G7
Square corner (modal)
G8
Arc tangent to previous path
G9
Arc defined by three points
G10
Mirror image cancellation
G11
Mirror image on the first axis of the channel
G12
Mirror image on the second axis of the channel
G13
Mirror image on the third axis of the channel
G14
Mirror image in the programmed directions
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G30
Polar origin preset
G31
Temporary polar origin shift to the center of arc
G33
Electronic threading with constant pitch
G34
Electronic threading with variable pitch
G36
Corner rounding, radius blend
G37
Tangential entry
G38
Tangential exit
G39
Corner chamfering
G40
Tool nose compensation cancel
G41
Tool Nose Compensation (TNC) Left
G42
Tool Nose Compensation (TNC) Right
G51
Smoothing Mode On
G53
Zero offset cancellation
G54
Select Work Coordinate System #1
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G60
Square corner (no-modal)
G61
Controlled corner rounding (no-modal)
G63
Rigid tapping
G66
Pattern repeat canned cycle
G68
Stock removal cycle along X axis
G69
Stock removal canned cycle along Z axis
G70
Select Inches
G71
Select Metric
G72
Scaling factor
G73
Pattern rotation
G74
Machine reference zero (home) search
G80
Canned Cycle Cancel
G81
Turning canned cycle with straight sections
G82
Facing canned cycle with straight sections
G83
Axial drilling and tapping canned cycle
G84
Turning canned cycle with arcs
G85
Facing canned cycle with arcs
G86
Longitudinal threading canned cycle
G87
Face threading canned cycle
G88
Grooving canned cycle along the X axis
G89
Grooving canned cycle along the Z axis
G90
Absolute programming
G91
Incremental programming
G92
Set Local Work Coordinate System
G93
Machining time in seconds
G94
Feed Per Minute Mode
G95
Feed Per Revolution
G96
Constant surface speed
G97
Constant turning speed
G151
Programming in diameters
G152
Programming in radius
G158
Incremental zero offset
G159
Additional absolute zero offsets
G192
Programming the turning speed limit
G261
Arc center in absolute coordinates (modal)
G262
Arc center referred to starting point
G263
Arc radius programming
M-Codes
Description
M0
Programmed stop
M1
Conditional program stop
M2
End of program
M3
Start the spindle clockwise
M4
Start the spindle counterclockwise
M5
Stop the spindle
M6
Tool change
M17
End of a global or local subroutine
M29
End of a global or local subroutine
M30
End of program and reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/fanuc/
TITLE: Fanuc
======================================================================
PDF
Simulation
Supported Controls
Fanuc
Fanuc
Subsections
Fanuc Milling
Fanuc Turning
Fanuc MX Turning
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/fanuc/fanuc-milling/
TITLE: Fanuc Milling
======================================================================
PDF
Simulation
Supported Controls
Fanuc
Fanuc Milling
Fanuc Milling
List of G and M-codes for Fanuc Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G5
AI contour control (high-precision contour control compatible command), High-speed cycle machining, High-speed binary program operation
G5_1
AI contour control / Nano smoothing / Smooth interpolation
G10
Programmable data input
G12_1
Polar coordinate interpolation mode
G13_1
Polar coordinate interpolation cancel mode
G15
Polar coordinates command cancel
G16
Polar coordinates command
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Input in inch
G21
Input in mm
G28
Automatic return to reference position
G30
2nd, 3rd and 4th reference position return
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G43
Tool length compensation +
G43_4
Tool center point control (type 1)
G43_5
Tool center point control (type 2)
G44
Tool length compensation -
G49
Tool length compensation cancel
G50_1
Programmable mirror image cancel
G51_1
Programmable mirror image
G52
Local coordinate system setting
G53
Machine coordinate system setting
G53_1
Tool-axis direction control
G53_6
Tool center point retention type tool axis direction control
G54
Workpiece coordinate system #1
G54_1
Additional workpiece coordinate systems
G54_2
Dynamic offsetting
G54_4
Workpiece setting error compensation
G55
Workpiece coordinate system #2
G56
Workpiece coordinate system #3
G57
Workpiece coordinate system #4
G58
Workpiece coordinate system #5
G59
Workpiece coordinate system #6
G65
Subprogram call with arguments
G66
Modal Subprogram set with arguments
G66_1
Modal Subprogram set with arguments
G67
Cancel modal subprogram call
G68
3-dimensional coordinate system conversion
G68_1
3-dimensional coordinate system conversion
G68_2
Tilted working plane command
G68_3
Tilted working plane command by tool axis direction
G68_4
Tilted working plane command (incremental multiple command)
G69
3-D coordinate conversion OFF
G73
High–Speed Peck Drilling Cycle
G74
Left–Handed Tapping Cycle
G76
Fine Boring Cycle
G80
Canned cycle cancel, Electronic gear box : synchronization cancellation
G81
Drilling Cycle, Spot Drilling
G82
Drilling Cycle, Counter Boring Cycle
G83
Peck Drilling Cycle
G84
Tapping cycle
G85
Boring cycle 1
G86
Boring cycle 2
G87
Boring cycle 2
G88
Boring cycle 3
G89
Boring cycle 4
G90
Absolute programming
G91
Incremental programming
G92_1
Workpiece Coordinate System Preset
G92
Work Coordinate Systems Shift Value
G94
Feed per minute
G95
Feed per revolution
G98
Canned cycle : return to initial level
G99
Canned cycle : return to R point level
G103
Toolbreakage check macro
G120
High speed mode cancel
G121
High speed mode
G130
High speed mode cancel
G131
High speed mode
G320
Specifying Automatic Centering/Automatic Measurement
G325
Automatic Tool Breakage Detection
G400
Yasda machine: measuring function
G500
Yasda machine: measuring function
G950
Machining levels setup
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M8
Coolant ON – Flood coolant
M9
Coolant Off
M13
Spindle ON clockwise/Coolant ON
M14
Spindle ON counterclockwise/Coolant ON
M30
End of program and reset
M31
??
M98
Subprogram call
M99
Subprogram end
M198
External subprogram call
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/fanuc/fanuc-mx-turning/
TITLE: Fanuc MX Turning
======================================================================
PDF
Simulation
Supported Controls
Fanuc
Fanuc MX Turning
Fanuc MX Turning
List of G and M-codes for Fanuc MX Turning as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid Motion Positioning
G1
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G4
Dwell
G7.1
(G107) Cylindrical interpolation
G10
Programmable data input
G12.1
Polar coordinate interpolation mode
G13.1
Polar coordinate interpolation cancel mode
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G28
Return To Machine Zero Point
G30
2nd, 3rd and 4th reference position return
G40
Tool nose compensation cancel
G41
Tool Nose Compensation (TNC) Left
G42
Tool Nose Compensation (TNC) Right
G50_1
Programmable mirror image cancel
G51_1
Programmable mirror image
G52
Set Local Work Coordinate System
G53
Machine coordinate system setting
G53_1
Tool-axis direction control
G54
Select Work Coordinate System #1
G54_1
Additional workpiece coordinate systems
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G65
Subprogram call with arguments
G68_2
Tilted working plane command
G80
Canned Cycle Cancel
G81
Drilling Cycle, Spot Drilling
G82
Drilling Cycle, Counter Boring Cycle
G83
Peck Drilling Cycle
G83.5
Front high-speed peck drilling cycle
G83.6
Front high-speed peck drilling cycle
G84
Tapping cycle
G85
Boring Cycle Face
G87
Drilling Cycle Side
G87.5
Side high-speed peck drilling cycle
G87.6
Side high-speed peck drilling cycle
G88
Tapping Cycle Side
G89
Bore In, Dwell, Bore Out Canned Cycle
G96
Turns on constant surface speed
G97
Cancels constant surface speed
G107
(G107) Cylindrical interpolation
G112
Polar coordinate interpolation mode
G113
Polar coordinate interpolation cancel mode
G400
Automatic tool offset compensation
G490
Automatic milling spindle orientation
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
ATC Tool Change command
M8
Coolant On
M9
Coolant Off
M13
Spindle ON clockwise/Coolant ON
M14
Spindle ON counterclockwise/Coolant ON
M30
End of program and reset
M68
Left chuck clamp
M69
Left chuck unclamp
M98
Subprogram call
M99
Subprogram end
M168
Right chuck clamp
M169
Right chuck unclamp
M203
Mill tool spindle forward
M204
Mill tool spindle reverse
M205
Mill tool spindle stop
M463
Left spindle forward & coolant on
M464
Left spindle reverse & coolant on
M465
Left spindle stop & coolant off
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/fanuc/fanuc-turning/
TITLE: Fanuc Turning
======================================================================
PDF
Simulation
Supported Controls
Fanuc
Fanuc Turning
Fanuc Turning
G and M-codes for Fanuc Turning as of CIMCO Edit 2026.01.09
G-Codes
System A
System B
System C
G0
Rapid Motion Positioning
Rapid Motion Positioning
Rapid Motion Positioning
G1
Linear Interpolation Motion
Linear Interpolation Motion
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
Circular Interpolation Motion CW
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
Circular Interpolation Motion CCW
Circular Interpolation Motion CCW
G4
Dwell
Dwell
Dwell
G7.1
(G107) Cylindrical interpolation
(G107) Cylindrical interpolation
(G107) Cylindrical interpolation
G10
Programmable data input
Programmable data input
Programmable data input
G12.1
Polar coordinate interpolation mode
Polar coordinate interpolation mode
Polar coordinate interpolation mode
G13.1
Polar coordinate interpolation cancel mode
Polar coordinate interpolation cancel mode
Polar coordinate interpolation cancel mode
G17
XY Plane Selection
XY Plane Selection
XY Plane Selection
G18
XZ Plane Selection
XZ Plane Selection
XZ Plane Selection
G19
YZ Plane Selection
YZ Plane Selection
YZ Plane Selection
G20
Select Inches
Select Inches
O.D./I.D. Turning Cycle
G21
Select Metric
Select Metric
Threading Cycle
G24
-
-
End Facing Cycle
G28
Return To Machine Zero Point
Return To Machine Zero Point
Return To Machine Zero Point
G28_2
Return To Machine Zero Point
Return To Machine Zero Point
Return To Machine Zero Point
G30
2nd, 3rd and 4th reference position return
2nd, 3rd and 4th reference position return
2nd, 3rd and 4th reference position return
G30_2
2nd, 3rd and 4th reference position return
2nd, 3rd and 4th reference position return
2nd, 3rd and 4th reference position return
G32
Thread Cutting
-
-
G33
-
Thread Cutting
Thread Cutting
G40
Tool nose compensation cancel
Tool nose compensation cancel
Tool nose compensation cancel
G41
Tool Nose Compensation (TNC) Left
Tool Nose Compensation (TNC) Left
Tool Nose Compensation (TNC) Left
G42
Tool Nose Compensation (TNC) Right
Tool Nose Compensation (TNC) Right
Tool Nose Compensation (TNC) Right
G43
Tool length compensation +
Tool length compensation +
Tool length compensation +
G43_4
Tool center point control (type 1)
Tool center point control (type 1)
Tool center point control (type 1)
G44
Tool length compensation -
Tool length compensation -
Tool length compensation -
G49
Tool length compensation cancel
Tool length compensation cancel
Tool length compensation cancel
G49_1
Tool length compensation cancel
Tool length compensation cancel
Tool length compensation cancel
G50_1
Programmable mirror image cancel
Programmable mirror image cancel
Programmable mirror image cancel
G50
Spindle Speed Maximum RPM Limit
Scaling cancel
Scaling cancel
G51_1
Programmable mirror image
Programmable mirror image
Programmable mirror image
G51
-
Scaling
Scaling
G52
Set Local Work Coordinate System
Set Local Work Coordinate System
Set Local Work Coordinate System
G53
Machine coordinate system setting
Machine coordinate system setting
Machine coordinate system setting
G53_1
Tool-axis direction control
Tool-axis direction control
Tool-axis direction control
G54
Select Work Coordinate System #1
Select Work Coordinate System #1
Select Work Coordinate System #1
G54_1
Additional workpiece coordinate systems
Additional workpiece coordinate systems
Additional workpiece coordinate systems
G55
Select Work Coordinate System #2
Select Work Coordinate System #2
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
Select Work Coordinate System #3
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
Select Work Coordinate System #4
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
Select Work Coordinate System #5
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
Select Work Coordinate System #6
Select Work Coordinate System #6
G65
Subprogram call with arguments
Subprogram call with arguments
Subprogram call with arguments
G68_2
Tilted working plane command
Tilted working plane command
Tilted working plane command
G69_1
3-D coordinate conversion OFF
3-D coordinate conversion OFF
3-D coordinate conversion OFF
G70
Finishing Cycle
Finishing Cycle
Select Inches
G71
O.D./I.D. Stock Removal Cycle
O.D./I.D. Stock Removal Cycle
Select Metric
G72
End Face Stock Removal Cycle
End Face Stock Removal Cycle
Finishing Cycle
G73
Pattern Repeating
Pattern Repeating
O.D./I.D. Stock Removal Cycle
G74
End Face Grooving Cycle
End Face Grooving Cycle
End Face Stock Removal Cycle
G75
O.D./I.D. Grooving Cycle
O.D./I.D. Grooving Cycle
Pattern Repeating
G76
Threading Cycle, Multiple Pass
Threading Cycle, Multiple Pass
End Face Grooving Cycle
G77
-
O.D./I.D. Turning Cycle
O.D./I.D. Grooving Cycle
G78
-
Threading Cycle
Threading Cycle, Multiple Pass
G79
-
End Facing Cycle
-
G80
Canned Cycle Cancel
Canned Cycle Cancel
Canned Cycle Cancel
G81
Drilling Cycle, Spot Drilling
Drilling Cycle, Spot Drilling
Drilling Cycle, Spot Drilling
G82
Drilling Cycle, Counter Boring Cycle
Drilling Cycle, Counter Boring Cycle
Drilling Cycle, Counter Boring Cycle
G83
Peck Drilling Cycle
Peck Drilling Cycle
Peck Drilling Cycle
G83.5
Front high-speed peck drilling cycle
Front high-speed peck drilling cycle
Front high-speed peck drilling cycle
G83.6
Front high-speed peck drilling cycle
Front high-speed peck drilling cycle
Front high-speed peck drilling cycle
G84
Tapping cycle
Tapping cycle
Tapping cycle
G85
Boring Cycle Face
Boring Cycle Face
Boring Cycle Face
G87
Drilling Cycle Side
Drilling Cycle Side
Drilling Cycle Side
G87.5
Side high-speed peck drilling cycle
Side high-speed peck drilling cycle
Side high-speed peck drilling cycle
G87.6
Side high-speed peck drilling cycle
Side high-speed peck drilling cycle
Side high-speed peck drilling cycle
G88
Tapping Cycle Side
Tapping Cycle Side
Tapping Cycle Side
G89
Bore In, Dwell, Bore Out Canned Cycle
Bore In, Dwell, Bore Out Canned Cycle
Bore In, Dwell, Bore Out Canned Cycle
G90
O.D./I.D. Turning Cycle
Absolute programming
Absolute programming
G91
-
Incremental programming
Incremental programming
G92
Threading Cycle
Spindle Speed Maximum RPM Limit
Spindle Speed Maximum RPM Limit
G94
End Facing Cycle
Feed Per Minute Mode
Feed Per Minute Mode
G95
-
Feed Per Revolution
Feed Per Revolution
G96
Turns on constant surface speed
Turns on constant surface speed
Turns on constant surface speed
G97
Cancels constant surface speed
Cancels constant surface speed
Cancels constant surface speed
G98
Feed Per Minute Mode
Canned cycle : return to initial level
Canned cycle : return to initial level
G99
Feed Per Revolution
Canned cycle : return to R point level
Canned cycle : return to R point level
G107
(G107) Cylindrical interpolation
(G107) Cylindrical interpolation
(G107) Cylindrical interpolation
G112
Polar coordinate interpolation mode
Polar coordinate interpolation mode
Polar coordinate interpolation mode
G113
Polar coordinate interpolation cancel mode
Polar coordinate interpolation cancel mode
Polar coordinate interpolation cancel mode
M-Codes
System A
System B
System C
M0
Programmed stop
Programmed stop
Programmed stop
M1
Optional stop
Optional stop
Optional stop
M2
End of program
End of program
End of program
M3
Spindle CW
Spindle CW
Spindle CW
M4
Spindle CCW
Spindle CCW
Spindle CCW
M5
Spindle Stop
Spindle Stop
Spindle Stop
M6
Tool Change
Tool Change
Tool Change
M8
Coolant On
Coolant On
Coolant On
M9
Coolant Off
Coolant Off
Coolant Off
M10
Main spindle clamp
Main spindle clamp
Main spindle clamp
M11
Main spindle unclamp
Main spindle unclamp
Main spindle unclamp
M13
Spindle ON clockwise/Coolant ON
Spindle ON clockwise/Coolant ON
Spindle ON clockwise/Coolant ON
M14
Spindle ON counterclockwise/Coolant ON
Spindle ON counterclockwise/Coolant ON
Spindle ON counterclockwise/Coolant ON
M30
End of program and reset
End of program and reset
End of program and reset
M83
Mill tool spindle forward
Mill tool spindle forward
Mill tool spindle forward
M84
Mill tool spindle reverse
Mill tool spindle reverse
Mill tool spindle reverse
M85
Mill tool spindle stop
Mill tool spindle stop
Mill tool spindle stop
M98
Subprogram call
Subprogram call
Subprogram call
M99
Subprogram end
Subprogram end
Subprogram end
M198
External subprogram call
External subprogram call
External subprogram call
M199
Subprogram end
Subprogram end
Subprogram end
M203
Mill tool spindle forward
Mill tool spindle forward
Mill tool spindle forward
M204
Mill tool spindle reverse
Mill tool spindle reverse
Mill tool spindle reverse
M205
Mill tool spindle stop
Mill tool spindle stop
Mill tool spindle stop
M210
Sub spindle clamp
Sub spindle clamp
Sub spindle clamp
M211
Sub spindle unclamp
Sub spindle unclamp
Sub spindle unclamp
M329
Rigid threading with heads
Rigid threading with heads
Rigid threading with heads
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/fidia/
TITLE: Fidia
======================================================================
PDF
Simulation
Supported Controls
Fidia
Fidia
Subsections
Fidia Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/fidia/fidia-milling/
TITLE: Fidia Milling
======================================================================
PDF
Simulation
Supported Controls
Fidia
Fidia Milling
Fidia Milling
List of G and M-codes for Fidia Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G6
Parabolic interpolation
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Cancels program rotation
G21
Program rotation
G22
Circular interpolation CW or helical interpolation CW
G23
Circular interpolation CW or helical interpolation CCW
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G43
3D radius compensation (opposite direction to vector)
G44
3D radius compensation (same direction as vector)
G54
Recording of work coordinate system origin
G55
Activate work coordinate system
G70
Input in inch
G71
Input in mm
G80
Canned cycle cancel, Electronic gear box : synchronization cancellation
G82
Fixed drilling cycle
G83
Fixed deep drilling cycle
G84
Fixed tapping cycle
G85
Fixed boring cycle
G86
Fixed boring cycle (variable diameter)
G87
Axis selection for fixed cycles
G90
Absolute programming
G91
Incremental programming
G92
Activating inverse RTCP
G93
Deactivating inverse RTCP
G182
Fixed drilling cycle
G183
Fixed deep drilling cycle
G184
Fixed tapping cycle
G185
Fixed boring cycle
G186
Fixed boring cycle (variable diameter)
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M8
Coolant ON – Flood coolant
M9
Coolant Off
M13
Spindle ON clockwise/Coolant ON
M14
Spindle ON counterclockwise/Coolant ON
M30
End of program and reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/flexium/
TITLE: Flexium
======================================================================
PDF
Simulation
Supported Controls
Flexium
Flexium
Subsections
Flexium Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/flexium/flexium-milling/
TITLE: Flexium Milling
======================================================================
PDF
Simulation
Supported Controls
Flexium
Flexium Milling
Flexium Milling
List of G and M-codes for Flexium Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G5
Programming a movement on the inclined axis
G10
Interruptible block
G16
Definition of the tool axis orientation with addresses P, Q, R
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Programming in polar coordinates (X, Z, C)
G21
Programming in cartesian coordinates (X, Y, Z)
G22
Programming in cylindrical coordinates (X, Y, Z)
G23
Circular interpolation defined by three points
G29
Tridimentional tool correction with 3 or 5 axes
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G43
Tridimensional tool correction with cylindrical tool
G53
Machine coordinate system setting
G54
Workpiece coordinate system #1
G55
Workpiece coordinate system #2
G56
Workpiece coordinate system #3
G57
Workpiece coordinate system #4
G58
Workpiece coordinate system #5
G59
Program origin offset
G70
Input in inch
G71
Input in mm
G77
Unconditional branch to a subroutine or sequence of blocks with return
G79
Conditional or unconditional jump to a sequence without return
G80
Canned cycle cancel, Electronic gear box : synchronization cancellation
G81
Drilling Cycle, Spot Drilling
G82
Drilling Cycle, Counter Boring Cycle
G83
Peck Drilling Cycle
G84
Tapping cycle
G85
Boring cycle 1
G86
Boring cycle 2
G87
Boring cycle 2
G88
Boring cycle 3
G89
Boring cycle 4
G90
Absolute programming
G91
Incremental programming
G92
Work Coordinate Systems Shift Value
G94
Feed per minute
G95
Feed per revolution
G151
Rotation around Tool Center Point
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M8
Coolant 1 on
M9
Coolant Off
M30
End of program and reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/haas/
TITLE: Haas
======================================================================
PDF
Simulation
Supported Controls
Haas
Haas
Subsections
Haas NGC Turning
Haas NGC Milling
Haas VR Milling
Haas UMC Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/haas/haas-ngc-milling/
TITLE: Haas NGC Milling
======================================================================
PDF
Simulation
Supported Controls
Haas
Haas NGC Milling
Haas NGC Milling
List of G and M-codes for Haas NGC Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid Motion Positioning
G1
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G4
Dwell
G10
Set Offsets
G12
Circular Pocket Milling CW
G13
Circular Pocket Milling CCW
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Select Inches
G21
Select Metric
G28
Return To Machine Zero Point
G40
Cutter Compensation Cancel
G41
2D Cutter Compensation Left
G42
2D Cutter Compensation Right
G43
Tool Length Compensation + (Add)
G44
Tool Length Compensation - (Subtract)
G47
Text Engraving
G49
G43/G44/G143 Cancel
G50
Cancel Scaling
G51
Scaling
G52
Set Work Coordinate System
G53
Machine coordinate system setting
G54
Select Work Coordinate System #1
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G65
Subprogram call with arguments
G68
Rotation
G69
Cancel G68 Rotation
G70
Bolt Hole Circle
G71
Bolt Hole Arc
G72
Bolt Holes Along an Angle
G73
High-Speed Peck Drilling Canned Cycle
G74
Reverse Tap Canned Cycle
G76
Fine Boring Canned Cycle
G77
Back Bore Canned Cycle
G80
Canned Cycle Cancel
G81
Drill Canned Cycle
G82
Spot Drill Canned Cycle
G83
Normal Peck Drilling Canned Cycle
G84
Tapping Canned Cycle
G85
Boring Canned Cycle
G86
Bore and Stop Canned Cycle
G87
Bore and Stop Canned Cycle
G89
Bore In, Dwell, Bore Out Canned Cycle
G90
Absolute programming
G91
Incremental programming
G92
Work Coordinate Systems Shift Value
G94
Feed Per Minute Mode
G95
Feed Per Revolution
G98
Canned Cycle Initial Point Return
G99
Canned Cycle R Plane Return
G100
Cancel Mirror Image
G101
Enable Mirror Image
G110
Select Work Coordinate System #7
G111
Select Work Coordinate System #8
G112
Select Work Coordinate System #9
G113
Select Work Coordinate System #10
G114
Select Work Coordinate System #11
G115
Select Work Coordinate System #12
G116
Select Work Coordinate System #13
G117
Select Work Coordinate System #14
G118
Select Work Coordinate System #15
G119
Select Work Coordinate System #16
G120
Select Work Coordinate System #17
G121
Select Work Coordinate System #18
G122
Select Work Coordinate System #19
G123
Select Work Coordinate System #20
G124
Select Work Coordinate System #21
G125
Select Work Coordinate System #22
G126
Select Work Coordinate System #23
G127
Select Work Coordinate System #24
G128
Select Work Coordinate System #25
G129
Select Work Coordinate System #26
G150
General Purpose Pocket Milling
G154
Select Work Coordinates P1-P99
G187
Setting the Smoothness Level
G234
Tool Center Point Control (TCPC)
G253
Orient Spindle Normal To Feature Coordinate System
G254
Dynamic Work Offset (DWO)
G255
Cancel Dynamic Work Offset (DWO)
G268
Feature Coordinate System command
G269
Cancel tilted plane
M-Codes
Description
M0
Stop Program
M1
Optional Program Stop
M2
Program End
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M7
Shower Coolant On
M8
Coolant On
M9
Coolant Off
M10
Engage 4th Axis Brake
M11
Release 4th Axis Brak
M12
Engage 5th Axis Brake
M13
Release 5th Axis Brake
M16
Tool Change
M19
Orient Spindle
M30
Program End and Reset
M56
Set Output Relay
M69
Clear Output Relay
M73
Tool Air Blast On
M74
Tool Air Blast Off
M83
Auto Air Gun On
M84
Auto Air Gun Off
M88
Through-Spindle Coolant On
M89
Through-Spindle Coolant Off
M96
Jump If No Input
M97
Local Subprogram Call
M98
Subprogram Call
M99
Subprogram Return / Jump / Loop
M109
Interactive User Input
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/haas/haas-ngc-turning/
TITLE: Haas NGC Turning
======================================================================
PDF
Simulation
Supported Controls
Haas
Haas NGC Turning
Haas NGC Turning
List of G and M-codes for Haas NGC Turning as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid Motion Positioning
G1
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G4
Dwell
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Select Inches
G21
Select Metric
G28
Return To Machine Zero Point
G30
Return To Reference position
G32
Thread Cutting
G40
Tool nose compensation cancel
G41
Tool Nose Compensation (TNC) Left
G42
Tool Nose Compensation (TNC) Right
G50
Spindle Speed Maximum RPM Limit
G52
Set Local Work Coordinate System
G53
Machine coordinate system setting
G54
Select Work Coordinate System #1
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G65
Subprogram call with arguments
G70
Finishing Cycle
G71
O.D./I.D. Stock Removal Cycle
G72
End Face Stock Removal Cycle
G73
Irregular Path Stock Removal
G74
End Face Grooving Cycle
G75
O.D./I.D. Grooving Cycle
G76
Threading Cycle, Multiple Pass
G80
Canned Cycle Cancel
G81
Drill Canned Cycle
G82
Spot Drill Canned Cycle
G83
Normal Peck Drilling Canned Cycle
G84
Tapping Canned Cycle
G85
Boring Canned Cycle
G86
Bore and Stop Canned Cycle
G89
Bore In, Dwell, Bore Out Canned Cycle
G90
O.D./I.D. Turning Cycle
G92
Threading Cycle
G94
End Facing Cycle
G95
Live Tooling Rigid Tap (Face)
G96
Turns on constant surface speed
G97
Cancels constant surface speed
G98
Feed Per Minute Mode
G99
Feed Per Revolution
G107
Cylindrical interpolation
G110
Select Work Coordinate System #7
G111
Select Work Coordinate System #8
G112
XY to XC Interpolation
G113
Cancel G112
G114
Select Work Coordinate System #9
G115
Select Work Coordinate System #10
G116
Select Work Coordinate System #11
G117
Select Work Coordinate System #12
G118
Select Work Coordinate System #13
G119
Select Work Coordinate System #14
G120
Select Work Coordinate System #15
G121
Select Work Coordinate System #16
G122
Select Work Coordinate System #17
G123
Select Work Coordinate System #18
G124
Select Work Coordinate System #19
G125
Select Work Coordinate System #20
G126
Select Work Coordinate System #21
G127
Select Work Coordinate System #22
G128
Select Work Coordinate System #23
G129
Select Work Coordinate System #24
G154
Select Work Coordinates P1-P99
G184
Reverse Tapping Canned Cycle For Left Hand Threads
G186
Reverse Live Tool Rigid Tap (For Left Hand Threads)
G187
Accuracy control
G195
Forward Live Tool Radial Tapping (Diameter)
G196
Reverse Live Tool Radial Tapping (Diameter)
G241
Radial Drill Canned Cycle
G242
Radial Spot Drill Canned Cycle
G243
Radial Normal Peck Drilling Canned Cycle
G245
Radial Boring Canned Cycle
G246
Radial Bore and Stop Canned Cycle
G249
Radial Bore and Dwell Canned Cycle
M-Codes
Description
M0
Stop Program
M1
Optional Program Stop
M2
Program End
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool change
M8
Coolant On
M9
Coolant Off
M10
Chuck clamp
M11
Chuck unclamp
M12
Auto Air Gun On
M13
Auto Air Gun Off
M19
Orient Spindle
M23
Chamfer Out of Thread On
M24
Chamfer Out of Thread Off
M30
Program End and Reset
M59
Set Output Relay
M69
Clear Output Relay
M88
High Pressure Coolant On
M89
High Pressure Coolant Off
M96
Jump If No Input
M97
Local Subprogram Call
M98
Subprogram Call
M99
Subprogram Return / Jump / Loop
M109
Interactive User Input
M110
Secondary Spindle Chuck Clamp (Optional)
M111
Secondary Spindle Chuck Unclamp (Optional)
M133
Live Tool Fwd (Optional)
M134
Live Tool Rev (Optional)
M135
Live Tool Stop (Optional)
M154
C-Axis Engage (Optional)
M155
C-Axis Disengage (Optional)
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/haas/haas-umc-milling/
TITLE: Haas UMC Milling
======================================================================
PDF
Simulation
Supported Controls
Haas
Haas UMC Milling
Haas UMC Milling
List of G and M-codes for Haas UMC Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid Motion Positioning
G1
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G4
Dwell
G10
Set Offsets
G12
Circular Pocket Milling CW
G13
Circular Pocket Milling CCW
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Select Inches
G21
Select Metric
G28
Return To Machine Zero Point
G40
Cutter Compensation Cancel
G41
2D Cutter Compensation Left
G42
2D Cutter Compensation Right
G43
Tool Length Compensation + (Add)
G44
Tool Length Compensation - (Subtract)
G47
Text Engraving
G49
G43/G44/G143 Cancel
G50
Cancel Scaling
G51
Scaling
G52
Set Work Coordinate System
G53
Machine coordinate system setting
G54
Select Work Coordinate System #1
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G65
Subprogram call with arguments
G68
Rotation
G69
Cancel G68 Rotation
G70
Bolt Hole Circle
G71
Bolt Hole Arc
G72
Bolt Holes Along an Angle
G73
High-Speed Peck Drilling Canned Cycle
G74
Reverse Tap Canned Cycle
G76
Fine Boring Canned Cycle
G77
Back Bore Canned Cycle
G80
Canned Cycle Cancel
G81
Drill Canned Cycle
G82
Spot Drill Canned Cycle
G83
Normal Peck Drilling Canned Cycle
G84
Tapping Canned Cycle
G85
Boring Canned Cycle
G86
Bore and Stop Canned Cycle
G87
Bore and Stop Canned Cycle
G89
Bore In, Dwell, Bore Out Canned Cycle
G90
Absolute programming
G91
Incremental programming
G92
Work Coordinate Systems Shift Value
G94
Feed Per Minute Mode
G95
Feed Per Revolution
G98
Canned Cycle Initial Point Return
G99
Canned Cycle R Plane Return
G100
Cancel Mirror Image
G101
Enable Mirror Image
G103
Limit Block Buffering
G110
Select Work Coordinate System #7
G111
Select Work Coordinate System #8
G112
Select Work Coordinate System #9
G113
Select Work Coordinate System #10
G114
Select Work Coordinate System #11
G115
Select Work Coordinate System #12
G116
Select Work Coordinate System #13
G117
Select Work Coordinate System #14
G118
Select Work Coordinate System #15
G119
Select Work Coordinate System #16
G120
Select Work Coordinate System #17
G121
Select Work Coordinate System #18
G122
Select Work Coordinate System #19
G123
Select Work Coordinate System #20
G124
Select Work Coordinate System #21
G125
Select Work Coordinate System #22
G126
Select Work Coordinate System #23
G127
Select Work Coordinate System #24
G128
Select Work Coordinate System #25
G129
Select Work Coordinate System #26
G150
General Purpose Pocket Milling
G154
Select Work Coordinates P1-P99
G187
Setting the Smoothness Level
G234
Tool Center Point Control (TCPC)
G254
Dynamic Work Offset (DWO)
G255
Cancel Dynamic Work Offset (DWO)
G268
Feature Coordinate System command
G269
Cancel tilted plane
M-Codes
Description
M0
Stop Program
M1
Optional Program Stop
M2
Program End
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M7
Shower Coolant On
M8
Coolant On
M9
Coolant Off
M10
Engage 4th Axis Brake
M11
Release 4th Axis Brak
M12
Engage 5th Axis Brake
M13
Release 5th Axis Brake
M16
Tool Change
M19
Orient Spindle
M30
Program End and Reset
M56
Set Output Relay
M69
Clear Output Relay
M73
Tool Air Blast On
M74
Tool Air Blast Off
M83
Auto Air Gun On
M84
Auto Air Gun Off
M88
Through-Spindle Coolant On
M89
Through-Spindle Coolant Off
M96
Jump If No Input
M97
Local Subprogram Call
M98
Subprogram Call
M99
Subprogram Return / Jump / Loop
M109
Interactive User Input
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/haas/haas-vr-milling/
TITLE: Haas VR Milling
======================================================================
PDF
Simulation
Supported Controls
Haas
Haas VR Milling
Haas VR Milling
List of G and M-codes for Haas VR Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid Motion Positioning
G1
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G4
Dwell
G10
Set Offsets
G12
Circular Pocket Milling CW
G13
Circular Pocket Milling CCW
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Select Inches
G21
Select Metric
G28
Return To Machine Zero Point
G40
Cutter Compensation Cancel
G41
2D Cutter Compensation Left
G42
2D Cutter Compensation Right
G43
Tool Length Compensation + (Add)
G44
Tool Length Compensation - (Subtract)
G47
Text Engraving
G49
G43/G44/G143 Cancel
G50
Cancel Scaling
G51
Scaling
G52
Set Work Coordinate System
G53
Machine coordinate system setting
G54
Select Work Coordinate System #1
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G65
Subprogram call with arguments
G68
Rotation
G69
Cancel G68 Rotation
G70
Bolt Hole Circle
G71
Bolt Hole Arc
G72
Bolt Holes Along an Angle
G73
High-Speed Peck Drilling Canned Cycle
G74
Reverse Tap Canned Cycle
G76
Fine Boring Canned Cycle
G77
Back Bore Canned Cycle
G80
Canned Cycle Cancel
G81
Drill Canned Cycle
G82
Spot Drill Canned Cycle
G83
Normal Peck Drilling Canned Cycle
G84
Tapping Canned Cycle
G85
Boring Canned Cycle
G86
Bore and Stop Canned Cycle
G87
Bore and Stop Canned Cycle
G89
Bore In, Dwell, Bore Out Canned Cycle
G90
Absolute programming
G91
Incremental programming
G92
Work Coordinate Systems Shift Value
G94
Feed Per Minute Mode
G95
Feed Per Revolution
G98
Canned Cycle Initial Point Return
G99
Canned Cycle R Plane Return
G100
Cancel Mirror Image
G101
Enable Mirror Image
G110
Select Work Coordinate System #7
G111
Select Work Coordinate System #8
G112
Select Work Coordinate System #9
G113
Select Work Coordinate System #10
G114
Select Work Coordinate System #11
G115
Select Work Coordinate System #12
G116
Select Work Coordinate System #13
G117
Select Work Coordinate System #14
G118
Select Work Coordinate System #15
G119
Select Work Coordinate System #16
G120
Select Work Coordinate System #17
G121
Select Work Coordinate System #18
G122
Select Work Coordinate System #19
G123
Select Work Coordinate System #20
G124
Select Work Coordinate System #21
G125
Select Work Coordinate System #22
G126
Select Work Coordinate System #23
G127
Select Work Coordinate System #24
G128
Select Work Coordinate System #25
G129
Select Work Coordinate System #26
G141
3D+ Cutter Compensation
G143
5-Axis Tool Length Compensation +
G150
General Purpose Pocket Milling
G153
5-Axis High Speed Peck Drilling Canned Cycle
G154
Select Work Coordinates P1-P99
G155
5-Axis Reverse Tap Canned Cycle
G161
5-Axis Drill Canned Cycle
G162
5-Axis Spot Drill Canned Cycle
G163
5-Axis Normal Peck Drilling Canned Cycle
G164
5-Axis Tapping Canned Cycle
G165
5-Axis Boring Canned Cycle
G166
5-Axis Bore and Stop Canned Cycle
G169
5-Axis Bore and Dwell Canned Cycle
G174
CCW Non-Vertical Rigid Tap
G184
CW Non-Vertical Rigid Tap
G187
Accuracy Control
G234
Tool Center Point Control (TCPC)
G253
Orient Spindle Normal To Feature Coordinate System
G254
Dynamic Work Offset (DWO)
G255
Cancel Dynamic Work Offset (DWO)
G268
Feature Coordinate System command
G269
Cancel tilted plane
M-Codes
Description
M0
Stop Program
M1
Optional Program Stop
M2
Program End
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M7
Shower Coolant On
M8
Coolant On
M9
Coolant Off
M10
Engage 4th Axis Brake
M11
Release 4th Axis Brak
M12
Engage 5th Axis Brake
M13
Release 5th Axis Brake
M16
Tool Change
M19
Orient Spindle
M30
Program End and Reset
M56
Set Output Relay
M69
Clear Output Relay
M73
Tool Air Blast On
M74
Tool Air Blast Off
M83
Auto Air Gun On
M84
Auto Air Gun Off
M88
Through-Spindle Coolant On
M89
Through-Spindle Coolant Off
M96
Jump If No Input
M97
Local Subprogram Call
M98
Subprogram Call
M99
Subprogram Return / Jump / Loop
M109
Interactive User Input
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/heidenhain/
TITLE: Heidenhain
======================================================================
PDF
Simulation
Supported Controls
Heidenhain
Heidenhain
Subsections
Heidenhain ISO Milling
Heidenhain Milling with Turning
Heidenhain Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/heidenhain/heidenhain-iso-milling/
TITLE: Heidenhain ISO Milling
======================================================================
PDF
Simulation
Supported Controls
Heidenhain
Heidenhain ISO Milling
Heidenhain ISO Milling
List of G and M-codes for Heidenhain ISO Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid positioning
G1
Linear cutting positioning
G2
Circular interpolation clockwise
G3
Circular interpolation clockwise
G4
Dwell time
G5
Circular interpolation, Cartesian coordinates, without indication of direction
G6
Circular arc with tangential connection to the preceding contour element
G7
Paraxial positioning block
G10
Straight-line interpolation, polar coordinates, rapid traverse
G11
Straight-line interpolation, polar coordinates, with feedrate
G12
Circular interpolation, polar coordinates, CW
G13
Circular interpolation, polar coordinates, CCW
G15
Circular interpolation, polar coordinates, without programmed direction
G16
Circular path with tangential connection
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G24
Chamfer between line segments
G25
Rounding between line segments
G26
Approaching on a straight line with tangential connection
G27
Departing on a straight line with tangential connection
G28
Mirror image
G29
Transfer the last nominal position value as a pole (circle center)
G30
Minimum point of the blank
G31
Maximum point of the blank
G36
Spindle orientation
G37
CONTOUR GEOMETRY
G38
STOP program run
G39
Subprogram call
G40
Disabled radius compensation
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G43
Paraxial compensation for G07, lengthening
G44
Paraxial compensation for G07, shortening
G51
Next tool number (with central tool file)
G53
Datum shift in datum table
G54
Datum shift in program
G55
Measure any coordinate
G62
Tolerance deviation for fast contour milling
G70
Input in inch
G71
Input in mm
G72
Scaling factor
G73
Pattern rotation
G79
Cycle call
G80
Tilting the working plane
G90
Absolute programming
G91
Incremental programming
G98
Subprogram label definition
G99
Tool definition
G120
Contour data
G121
PILOT DRILLING
G122
ROUGH-OUT
G123
FLOOR FINISHING
G124
SIDE FINISHING
G200
Drilling
G201
Reaming
G202
Boring
G203
Universal drilling
G204
Back boring
G205
Universal pecking
G206
Tapping New with a floating tap holder
G207
Rigid Tapping without a floating tap holder New
G208
Bore milling
G209
Tapping with chip breaking
G220
Polar pattern
G221
Cartesian pattern
G230
Multipass milling
G231
Ruled surface
G232
Face milling
G233
Face milling
G240
Single-lip deep hole drilling
G241
Single-lip deep hole drilling
G247
Datum setting
G251
Rectangular pocket
G252
Circular pocket
G253
Slot milling
G254
Slot milling
G256
Rectangular stud finishing
G257
Circular pocket finishing
G262
Thread milling
G263
THREAD MILLING/COUNTERSINKING
G264
Thread milling
G265
Thread milling
G267
Thread milling
G302
Head orientation
G309
Tolerance
G326
Tolerance
G327
???
G330
???
G332
Tuning
G400
Basic rotation
G401
Basic rotation from 2 holes
G402
Basic rotation over 2 studs
G403
Basic rotation compensation via rotary axis
G404
SET BASIC ROTATION
G405
Compensating workpiece misalignment by rotating the C-axis
G408
SLOT CENTER REF PT
G409
RIDGE CENTER REF PT
G410
DATUM FROM INSIDE OF RECTANGLE
G411
DATUM FROM OUTSIDE OF RECTANGLE
G412
DATUM FROM INSIDE OF CIRCLE
G413
DATUM FROM OUTSIDE OF CIRCLE
G414
DATUM FROM OUTSIDE OF CORNER
G415
DATUM FROM INSIDE OF CORNER
G416
DATUM CIRCLE CENTER
G417
DATUM IN TOUCH PROBE AXIS
G418
DATUM AT CENTER OF 4 HOLES
G419
DATUM IN ONE AXIS
G420
MEASURE ANGLE
G421
MEASURE HOLE
G422
MEAS. CIRCLE OUTSIDE
G423
MEAS. RECTAN. INSIDE
G424
MEASURE RECTANGLE OUTSIDE
G425
MEASURE INSIDE WIDTH
G426
MEASURE RIDGE WIDTH
G427
MEASURE COORDINATE
G430
MEASURE BOLT HOLE CIRCLE
G431
MEASURE PLANE
G441
Fast probing
G480
Calibrate the TT
G481
Measure the tool length
G482
Measure the tool radius
G483
Measure the tool length and radius
M-Codes
Description
M0
Program STOP, Spindle STOP
M1
Optional program STOP
M2
Program end
M3
Spindle ON clockwise
M4
Spindle ON counterclockwise
M5
Spindle STOP
M8
Coolant On
M9
Coolant Off
M13
Spindle ON clockwise/Coolant ON
M14
Spindle ON counterclockwise/Coolant ON
M30
End of program and reset
M89
Cycle call in every block until M99 or new cycle def is called
M91
Machine datum coordinates
M92
Additional machine datum coordinates
M94
Reduce display value of rotary axes
M99
Blockwise cycle call
M126
Shortest-path traverse of rotary axes
M127
Reset M126
M128
Tool center point management
M129
Reset M128
M130
Moving to positions in a non-tilted coordinate system with a tilted working plane
M140
Retraction from the contour in the tool-axis direction
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/heidenhain/heidenhain-milling-with-turning/
TITLE: Heidenhain Milling with Turning
======================================================================
PDF
Simulation
Supported Controls
Heidenhain
Heidenhain Milling with Turning
Heidenhain Milling with Turning
List of M-codes for Heidenhain Milling with Turning as of CIMCO Edit 2026.01.09
M-Codes
Description
M0
Program STOP, Spindle STOP
M1
Optional program STOP
M2
Program end
M3
Spindle ON clockwise
M4
Spindle ON counterclockwise
M5
Spindle STOP
M8
Coolant On
M9
Coolant Off
M13
Spindle ON clockwise/Coolant ON
M14
Spindle ON counterclockwise/Coolant ON
M30
End of program and reset
M89
Cycle call in every block until M99 or new cycle def is called
M91
Machine datum coordinates
M92
Additional machine datum coordinates
M94
Reduce display value of rotary axes
M99
Blockwise cycle call
M126
Shortest-path traverse of rotary axes
M127
Reset M126
M128
Tool center point management
M129
Reset M128
M130
Moving to positions in a non-tilted coordinate system with a tilted working plane
M136
Feed in mm/rev
M137
Feed in mm/min
M138
Axes the TNC has available to calculate the result of a rotation
M140
Retraction from the contour in the tool-axis direction
M303
Workpiece spindle clockwise rotation
M304
Workpiece spindle counter-clockwise rotation
M305
Spindle Stop
M319
Workpiece spindle orientation
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/heidenhain/heidenhain-milling/
TITLE: Heidenhain Milling
======================================================================
PDF
Simulation
Supported Controls
Heidenhain
Heidenhain Milling
Heidenhain Milling
List of M-codes for Heidenhain Milling as of CIMCO Edit 2026.01.09
M-Codes
Description
M0
Program STOP, Spindle STOP
M1
Optional program STOP
M2
Program end
M3
Spindle ON clockwise
M4
Spindle ON counterclockwise
M5
Spindle STOP
M8
Coolant On
M9
Coolant Off
M13
Spindle ON clockwise/Coolant ON
M14
Spindle ON counterclockwise/Coolant ON
M30
End of program and reset
M89
Cycle call in every block until M99 or new cycle def is called
M91
Machine datum coordinates
M92
Additional machine datum coordinates
M94
Reduce display value of rotary axes
M99
Blockwise cycle call
M126
Shortest-path traverse of rotary axes
M127
Reset M126
M128
Tool center point management
M129
Reset M128
M130
Moving to positions in a non-tilted coordinate system with a tilted working plane
M138
Axes the TNC has available to calculate the result of a rotation
M140
Retraction from the contour in the tool-axis direction
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/hurco/
TITLE: Hurco
======================================================================
PDF
Simulation
Supported Controls
Hurco
Hurco
Subsections
Hurco Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/hurco/hurco-milling/
TITLE: Hurco Milling
======================================================================
PDF
Simulation
Supported Controls
Hurco
Hurco Milling
Hurco Milling
List of G and M-codes for Hurco Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G2_4
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G3_4
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G5_1
Surface Finish
G5_2
Data smoothing
G5_3
Surface finish quality
G8_1
ASR Command Buffer On
G8_2
ASR Command Buffer Off
G10
Programmable data input
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Input in inch
G21
Input in mm
G28
Automatic return to reference position
G30
2nd, 3rd and 4th reference position return
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G43
Tool length compensation +
G43_4
5-Axis Linear Interpolation
G44
Tool length compensation -
G49
Tool length compensation cancel
G52
Local coordinate system setting
G53
Machine coordinate system setting
G54
Workpiece coordinate system #1
G54_1
Additional workpiece coordinate systems
G54_2
Additional workpiece coordinate systems
G55
Workpiece coordinate system #2
G56
Workpiece coordinate system #3
G57
Workpiece coordinate system #4
G58
Workpiece coordinate system #5
G59
Workpiece coordinate system #6
G65
Subprogram call with arguments
G68
3-dimensional coordinate system conversion
G68_2
Tilted working plane command
G68_3
Local Rotation NC Transform Plane
G69
3-D coordinate conversion OFF
G69_1
Cancel All Active Transform Planes
G73
High–Speed Peck Drilling Cycle
G74
Left–Handed Tapping Cycle
G76
Fine Boring Cycle
G80
Canned cycle cancel, Electronic gear box : synchronization cancellation
G81
Drilling Cycle, Spot Drilling
G82
Drilling Cycle, Counter Boring Cycle
G83
Peck Drilling Cycle
G84
Tapping cycle
G84_2
Rigid Tapping Cycle
G84_3
Rigid Tapping Cycle
G85
Boring cycle 1
G86
Boring cycle 2
G87
Boring cycle 2
G88
Boring cycle 3
G89
Boring cycle 4
G90
Absolute programming
G91
Incremental programming
G92
Work Coordinate Systems Shift Value
G92_1
Workpiece Coordinate System Preset
G94
Feed per minute
G95
Feed per revolution
G98
Canned cycle : return to initial level
G99
Canned cycle : return to R point level
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M7
Switches on secondary coolant systems
M8
Switches on primary coolant system
M9
Switches off both the primary and secondary coolant
M30
End of program and reset
M31
??
M98
Subprogram call
M99
Subprogram end
M126
Shortest Rotary Angle Path Traverse
M127
Cancels Shortest Rotary Angle Path Traverse (M126)
M128
Tool Center Point Management
M129
Cancels Tool Center Point Management (M128)
M140
Retraction from the contour in the tool-axis direction
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/mazak/
TITLE: Mazak
======================================================================
PDF
Simulation
Supported Controls
Mazak
Mazak
Subsections
Mazak Turning
Mazak Integrex
Mazak Milling
Mazak SmoothAi Milling
Mazak SmoothAi Milling with Turning
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/mazak/mazak-integrex/
TITLE: Mazak Integrex
======================================================================
PDF
Simulation
Supported Controls
Mazak
Mazak Integrex
Mazak Integrex
List of G and M-codes for Mazak Integrex as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid Motion Positioning
G1
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G4
Dwell
G5
High-speed machining mode
G7.1
Cylindrical interpolation
G10.9
Selection between diameter and radius data input
G12.1
Milling interpolation ON
G13.1
Milling interpolation OFF
G15
Polar coordinate interpolation OFF
G16
Polar coordinate interpolation ON
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Select Inches
G21
Select Metric
G28
Return To Machine Zero Point
G30
2nd, 3rd and 4th reference position return
G32
Thread Cutting
G33
Thread Cutting
G40
Tool nose compensation cancel
G41
Tool Nose Compensation (TNC) Left
G41.2
Tool radius compensation for five-axis machining (left)
G42
Tool Nose Compensation (TNC) Right
G42.2
Tool radius compensation for five-axis machining (right)
G43
Tool length compensation +
G43.1
Tool length offset in tool-axis direction
G43.4
Tool center point control (type 1)
G43.5
Tool center point control (type 2)
G49
Tool length compensation cancel
G53
Machine coordinate system setting
G53.1
Tool-axis direction control
G54
Select Work Coordinate System #1
G54.1
Selection of additional workpiece coordinate systems
G54.2
Dynamic offsetting II
G54.4
Workpiece setup error correction
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G65
Subprogram call with arguments
G68
3-D coordinate conversion ON
G68.2
Inclined-plane machining ON
G68.3
Inclined-plane machining (by specifying tool-axis direction) ON
G69
3-D coordinate conversion OFF
G73
Fixed cycle (High-speed deep-hole drilling)
G74
Fixed cycle (Reverse tapping)
G75
Fixed cycle (Boring 1)
G77
Fixed cycle (Back spot facing)
G80
Fixed cycle OFF
G81
Drilling Cycle, Spot Drilling
G82
Drilling Cycle, Counter Boring Cycle
G82.2
Drilling Cycle, Counter Boring Cycle
G83
Front drill cycle
G84
Front tap cycle
G84.2
Front synchronous tap cycle
G84.3
Synchronous reverse tapping
G85
Front boring cycle
G87
Side drill cycle
G88
Side tap cycle
G89
Side boring cycle
G90
Absolute programming
G91
Incremental programming
G92
Spindle Speed Maximum RPM Limit
G94
Feed Per Minute Mode
G95
Feed Per Revolution
G96
Turns on constant surface speed
G97
Cancels constant surface speed
G98
Initial point level return
G99
R-point level return
G270
Finishing Cycle
G271
Longitudinal rough cutting cycle
G272
Transverse roughing cycle (leaving finishing allowance)
G273
Formed material rough cutting cycle
G274
Longitudinal cut-off cycle
G275
Transverse cut-off cycle
G276
Compound thread cutting cycle
G283
Front drill cycle
G284
Front tap cycle
G285
Front boring cycle
G290
Longitudinal turning cycle
G292
Thread Cutting
G294
End Facing Cycle
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M8
Coolant On
M9
Coolant Off
M30
End of program and reset
M98
Subprogram call
M99
Subprogram end
M198
External subprogram call
M199
External subprogram call
M203
Milling tool normal rotation
M204
Milling tool reverse rotation
M205
Milling tool stop
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/mazak/mazak-milling/
TITLE: Mazak Milling
======================================================================
PDF
Simulation
Supported Controls
Mazak
Mazak Milling
Mazak Milling
List of G and M-codes for Mazak Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G10
Data setting mode ON
G12_1
Polar Coordinate Interpolation ON
G13_1
Polar Coordinate Interpolation OFF
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Inch command
G21
Metric command
G28
Reference point return
G30
Return to 2nd, 3rd and 4th reference points
G34_1
Hole machining pattern cycle (on a circle)
G35
Hole machining pattern cycle (on a line)
G36
Hole machining pattern cycle (on an arc)
G37_1
Hole machining pattern cycle (on a grid)
G40
Tool radius compensation OFF
G41
Tool radius compensation (left)
G42
Tool radius compensation (right)
G43
Tool length offset (+)
G43_4
Tool center point control (type 1)
G43_5
Tool center point control (type 2)
G44
Tool length offset (-)
G49
Tool length compensation cancel
G52
Local coordinate system setting
G53
Machine coordinate system selection
G53_1
Tool-axis direction control
G54
Select Work Coordinate System #1
G54_1
Additional workpiece coordinate systems
G54_2
Selection of fixture offset
G54_4
Workpiece setup error correction
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G65
Subprogram call with arguments
G66
Modal Subprogram set with arguments
G66_1
Modal Subprogram set with arguments
G67
Cancel modal subprogram call
G68
3-dimensional coordinate system conversion
G68_2
Inclined-plane machining ON
G68_3
Inclined-plane machining (by specifying tool-axis direction) ON
G68_4
Incremental coordinate system establishment for inclined-plane machining
G69
3-D coordinate conversion OFF
G73
Fixed cycle (High-speed deep-hole drilling)
G74
Fixed cycle (Reverse tapping)
G75
Fixed cycle (Boring 1)
G76
Fixed cycle (Boring 2)
G77
Fixed cycle (Back spot facing)
G78
Fixed cycle (Boring 3)
G79
Fixed cycle (Boring 4)
G80
Fixed cycle OFF
G81
Fixed cycle (Spot drilling)
G82
Fixed cycle (Drilling)
G83
Fixed cycle (Deep-hole drilling)
G84
Fixed cycle (Tapping)
G84_2
Fixed cycle (Synchronous tapping)
G84_3
Fixed cycle (Synchronous reverse tapping)
G85
Fixed cycle (Reaming)
G86
Fixed cycle (Boring 5)
G87
Fixed cycle (Back boring)
G88
Fixed cycle (Boring 6)
G89
Fixed cycle (Boring 7)
G90
Absolute programming
G91
Incremental programming
G92
Coordinate System Setting
G94
Feed per minute (asynchronous)
G95
Feed per revolution (synchronous)
G98
Initial point level return in fixed cycles
G99
R-point level return in fixed cycles
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
Program end
M3
Start of forward milling spindle rotation
M4
Start of backward milling spindle rotation
M5
Stop of milling spindle rotation
M6
Tool Change
M8
Coolant On
M9
Coolant Off
M30
End of program and reset
M98
Subprogram call
M99
Subprogram Return / Loop
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/mazak/mazak-smoothai-milling-with-turning/
TITLE: Mazak SmoothAi Milling with Turning
======================================================================
PDF
Simulation
Supported Controls
Mazak
Mazak SmoothAi Milling with Turning
Mazak SmoothAi Milling with Turning
List of G and M-codes for Mazak SmoothAi Milling with Turning as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G5
High-speed machining mode
G10
Data setting mode ON
G10_9
Selection between diameter and radius data input
G12
Circle Cutting CW
G12_1
Polar Coordinate Interpolation ON
G13
Circle Cutting CCW
G13_1
Polar Coordinate Interpolation OFF
G17
XY Plane Selection
G18
XZ Plane Selection
G18_1
Milling mode selection (Turning mode OFF)
G18_2
Selection of turning plane for A-axis positioning to 0 (for machining on the positive side of the Y-axis in the machine coordinate system)
G18_3
Selection of turning plane for A-axis positioning to -90
G18_4
Selection of turning plane for A-axis positioning to 0 (for machining on the negative side of the Y-axis in the machine coordinate system)
G18_9
Temporary cancellation of G18.2/G18.3/G18.4
G19
YZ Plane Selection
G20
Inch command
G21
Metric command
G28
Reference point return
G30
Return to 2nd, 3rd and 4th reference points
G34_1
Hole machining pattern cycle (on a circle)
G35
Hole machining pattern cycle (on a line)
G36
Hole machining pattern cycle (on an arc)
G37_1
Hole machining pattern cycle (on a grid)
G40
Tool radius compensation OFF
G41
Tool radius compensation (left)
G42
Tool radius compensation (right)
G43
Tool length offset (+)
G43_4
Tool tip point control (type 1)
G43_5
Tool tip point control (type 2)
G44
Tool length offset (-)
G49
Tool length compensation cancel
G52
Local coordinate system setting
G53
Machine coordinate system selection
G53_1
Tool-axis direction control
G54
Select Work Coordinate System #1
G54_1
Additional workpiece coordinate systems
G54_2
Selection of fixture offset
G54_4
Workpiece setup error correction
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G61_1
High-accuracy mode (Geometry compensation)
G65
Subprogram call with arguments
G66
Modal Subprogram set with arguments
G66_1
Modal Subprogram set with arguments
G67
Cancel modal subprogram call
G68
3-dimensional coordinate system conversion
G68_2
Inclined-plane machining ON
G68_3
Inclined-plane machining (by specifying tool-axis direction) ON
G68_4
Incremental coordinate system establishment for inclined-plane machining
G69
3-D coordinate conversion OFF
G73
Fixed cycle (High-speed deep-hole drilling)
G74
Fixed cycle (Reverse tapping)
G75
Fixed cycle (Boring 1)
G76
Fixed cycle (Boring 2)
G77
Fixed cycle (Back spot facing)
G78
Fixed cycle (Boring 3)
G79
Fixed cycle (Boring 4)
G80
Fixed cycle OFF
G81
Fixed cycle (Spot drilling)
G82
Fixed cycle (Drilling)
G83
Fixed cycle (Deep-hole drilling)
G84
Fixed cycle (Tapping)
G84_2
Fixed cycle (Synchronous tapping)
G84_3
Fixed cycle (Synchronous reverse tapping)
G85
Fixed cycle (Reaming)
G86
Fixed cycle (Boring 5)
G87
Fixed cycle (Back boring)
G88
Fixed cycle (Boring 6)
G89
Fixed cycle (Boring 7)
G90
Absolute programming
G91
Incremental programming
G92
Spindle Speed Maximum RPM Limit
G94
Feed per minute (asynchronous)
G95
Feed per revolution (synchronous)
G96
Turns on constant surface speed
G97
Cancels constant surface speed
G98
Initial point level return in fixed cycles
G99
R-point level return in fixed cycles
G270
Finishing Cycle
G271
Longitudinal rough cutting cycle
G272
Transverse roughing cycle (leaving finishing allowance)
G273
Formed material rough cutting cycle
G274
Longitudinal cut-off cycle
G275
Transverse cut-off cycle
G276
Compound thread cutting cycle
G290
Longitudinal turning cycle
G292
Thread Cutting
G294
End Facing Cycle
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
Program end
M3
Start of forward milling spindle rotation
M4
Start of backward milling spindle rotation
M5
Stop of milling spindle rotation
M6
Tool Change
M8
Coolant On
M9
Coolant Off
M30
End of program and reset
M98
Subprogram call
M99
Subprogram Return / Loop
M203
Milling tool normal rotation
M204
Milling tool reverse rotation
M205
Milling tool stop
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/mazak/mazak-smoothai-milling/
TITLE: Mazak SmoothAi Milling
======================================================================
PDF
Simulation
Supported Controls
Mazak
Mazak SmoothAi Milling
Mazak SmoothAi Milling
List of G and M-codes for Mazak SmoothAi Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G5
High-speed machining mode
G10
Data setting mode ON
G12
Circle Cutting CW
G12_1
Polar Coordinate Interpolation ON
G13
Circle Cutting CCW
G13_1
Polar Coordinate Interpolation OFF
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Inch command
G21
Metric command
G28
Reference point return
G30
Return to 2nd, 3rd and 4th reference points
G34_1
Hole machining pattern cycle (on a circle)
G35
Hole machining pattern cycle (on a line)
G36
Hole machining pattern cycle (on an arc)
G37_1
Hole machining pattern cycle (on a grid)
G40
Tool radius compensation OFF
G41
Tool radius compensation (left)
G42
Tool radius compensation (right)
G43
Tool length offset (+)
G43_4
Tool tip point control (type 1)
G43_5
Tool tip point control (type 2)
G44
Tool length offset (-)
G49
Tool length compensation cancel
G52
Local coordinate system setting
G53
Machine coordinate system selection
G53_1
Tool-axis direction control
G54
Select Work Coordinate System #1
G54_1
Additional workpiece coordinate systems
G54_2
Selection of fixture offset
G54_4
Workpiece setup error correction
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G61_1
High-accuracy mode (Geometry compensation)
G65
Subprogram call with arguments
G66
Modal Subprogram set with arguments
G66_1
Modal Subprogram set with arguments
G67
Cancel modal subprogram call
G68
3-dimensional coordinate system conversion
G68_2
Inclined-plane machining ON
G68_3
Inclined-plane machining (by specifying tool-axis direction) ON
G68_4
Incremental coordinate system establishment for inclined-plane machining
G69
3-D coordinate conversion OFF
G73
Fixed cycle (High-speed deep-hole drilling)
G74
Fixed cycle (Reverse tapping)
G75
Fixed cycle (Boring 1)
G76
Fixed cycle (Boring 2)
G77
Fixed cycle (Back spot facing)
G78
Fixed cycle (Boring 3)
G79
Fixed cycle (Boring 4)
G80
Fixed cycle OFF
G81
Fixed cycle (Spot drilling)
G82
Fixed cycle (Drilling)
G83
Fixed cycle (Deep-hole drilling)
G84
Fixed cycle (Tapping)
G84_2
Fixed cycle (Synchronous tapping)
G84_3
Fixed cycle (Synchronous reverse tapping)
G85
Fixed cycle (Reaming)
G86
Fixed cycle (Boring 5)
G87
Fixed cycle (Back boring)
G88
Fixed cycle (Boring 6)
G89
Fixed cycle (Boring 7)
G90
Absolute programming
G91
Incremental programming
G92
Coordinate System Setting
G94
Feed per minute (asynchronous)
G95
Feed per revolution (synchronous)
G98
Initial point level return in fixed cycles
G99
R-point level return in fixed cycles
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
Program end
M3
Start of forward milling spindle rotation
M4
Start of backward milling spindle rotation
M5
Stop of milling spindle rotation
M6
Tool Change
M8
Coolant On
M9
Coolant Off
M30
End of program and reset
M98
Subprogram call
M99
Subprogram Return / Loop
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/mazak/mazak-turning/
TITLE: Mazak Turning
======================================================================
PDF
Simulation
Supported Controls
Mazak
Mazak Turning
Mazak Turning
List of G and M-codes for Mazak Turning as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid Motion Positioning
G1
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G4
Dwell
G7.1
(G107) Cylindrical interpolation
G10
Programmable data input
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G28
Return To Machine Zero Point
G30
2nd, 3rd and 4th reference position return
G30.1
Return to floating reference point
G40
Tool nose compensation cancel
G41
Tool Nose Compensation (TNC) Left
G42
Tool Nose Compensation (TNC) Right
G46
Tool nose radius compensation (automatic direction selection) ON
G54
Select Work Coordinate System #1
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G65
Subprogram call with arguments
G66
Modal Subprogram set with arguments
G66_1
Modal Subprogram set with arguments
G67
Cancel modal subprogram call
G80
Canned Cycle Cancel
G83
Front drill cycle
G84
Front tap cycle
G84.2
Front synchronous tap cycle
G85
Front boring cycle
G87
Side drill cycle
G88
Side tap cycle
G88.2
Side synchronous tap cycle
G89
Side boring cycle
G96
Turns on constant surface speed
G97
Cancels constant surface speed
G107
(G107) Cylindrical interpolation
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M8
Coolant On
M9
Coolant Off
M30
End of program and reset
M98
Subprogram call
M99
Subprogram end
M198
External subprogram call
M199
External subprogram call
M203
Milling tool normal rotation
M204
Milling tool reverse rotation
M205
Milling tool stop
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/mitsubishi/
TITLE: Mitsubishi
======================================================================
PDF
Simulation
Supported Controls
Mitsubishi
Mitsubishi
Subsections
Mitsubishi Turning
Mitsubishi Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/mitsubishi/mitsubishi-milling/
TITLE: Mitsubishi Milling
======================================================================
PDF
Simulation
Supported Controls
Mitsubishi
Mitsubishi Milling
Mitsubishi Milling
List of G and M-codes for Mitsubishi Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW
G3
Circular interpolation CCW
G4
Dwell (Time-based Designation)
G10
Programmable data input
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Inch command
G21
Metric command
G28
Reference position return completed
G30
2nd to 4th reference position return
G34
Special fixed cycle (bolt hole circle)
G35
Special fixed cycle (line at angle)
G36
Special fixed cycle (arc)
G37_1
Special fixed cycle (grid)
G40
Tool radius compensation cancel
G41
Tool radius compensation left
G42
Tool radius compensation right
G43
Tool length compensation +
G43_4
Tool center point control type1 ON
G44
Tool length compensation -
G49
Tool length compensation cancel, Tool center point control cancel
G52
Local coordinate system setting
G53
Basic machine coordinate system selection
G53_1
Tool axis direction control (type 1)
G54
Workpiece coordinate system 1 selection
G54_1
Extended workpiece coordinate system selection
G55
Workpiece coordinate system 2 selection
G56
Workpiece coordinate system 3 selection
G57
Workpiece coordinate system 4 selection
G58
Workpiece coordinate system 5 selection
G59
Workpiece coordinate system 6 selection
G65
Subprogram call with arguments
G68_2
Inclined surface machining command
G69
3-dimensional coordinate conversion mode OFF, Cancel inclined surface machining command
G73
Fixed cycle (stepping cycle)
G74
Fixed cycle (reverse tap)
G76
Fixed cycle (Fine boring)
G80
Fixed cycle cancel
G81
Fixed cycle (drill/spot drill)
G82
Fixed cycle (drill/counter boring)
G83
Fixed cycle (deep drilling/small-diameter deep-hole drilling)
G84
Fixed cycle (tapping)
G85
Fixed cycle (boring)
G86
Fixed cycle (boring)
G87
Fixed cycle (back boring)
G88
Fixed cycle (boring)
G89
Fixed cycle (boring)
G90
Absolute value command
G91
Incremental value command
G92_1
Workpiece Coordinate System Preset
G92
Coordinate System Setting
G94
Feed per minute (asynchronous feed)
G95
Feed per revolution (synchronous feed)
G98
Fixed cycle Initial level return
G99
Fixed cycle R point level return
M-Codes
Description
M0
Program stop
M1
Optional stop
M2
Program end
M3
Start of forward milling spindle rotation
M4
Start of backward milling spindle rotation
M5
Stop of milling spindle rotation
M6
Tool Change
M8
Coolant On
M9
Coolant Off
M30
End of program and reset
M98
Subprogram call
M99
Subprogram end
M198
Subprogram call from SD card
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/mitsubishi/mitsubishi-turning/
TITLE: Mitsubishi Turning
======================================================================
PDF
Simulation
Supported Controls
Mitsubishi
Mitsubishi Turning
Mitsubishi Turning
List of G and M-codes for Mitsubishi Turning as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid Motion Positioning
G1
Linear Interpolation Motion
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G4
Dwell
G7.1
(G107) Cylindrical interpolation
G8
High speed machining
G10
Programmable data input
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Select Inches
G21
Select Metric
G28
Return To Machine Zero Point
G30
2nd, 3rd and 4th reference position return
G40
Tool nose compensation cancel
G41
Tool Nose Compensation (TNC) Left
G42
Tool Nose Compensation (TNC) Right
G50
Spindle Speed Maximum RPM Limit
G52
Local coordinate system setting
G53
Basic machine coordinate system selection
G54
Select Work Coordinate System #1
G55
Select Work Coordinate System #2
G56
Select Work Coordinate System #3
G57
Select Work Coordinate System #4
G58
Select Work Coordinate System #5
G59
Select Work Coordinate System #6
G65
User macro call
G70
Finishing Cycle
G71
Longitudinal rough cutting cycle
G72
Face rough cutting cycle
G73
Formed material rough cutting cycle
G74
Face cut-off cycle
G75
Longitudinal cut-off cycle
G76
Compound thread cutting cycle
G76.1
2-part System Synchronous Thread Cutting Cycle I
G76.2
2-part System Synchronous Thread Cutting Cycle II
G80
Canned Cycle Cancel
G81
Drilling Cycle, Spot Drilling
G82
Drilling Cycle, Counter Boring Cycle
G83
Peck Drilling Cycle
G84
Tapping cycle
G85
Boring Cycle Face
G87
Drilling Cycle Side
G88
Tapping Cycle Side
G89
Bore In, Dwell, Bore Out Canned Cycle
G96
Constant surface speed control ON
G97
Constant surface speed control OFF
G107
(G107) Cylindrical interpolation
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M8
Coolant On
M9
Coolant Off
M13
Spindle ON clockwise/Coolant ON
M14
Spindle ON counterclockwise/Coolant ON
M23
2nd Spindle CW
M24
2nd Spindle CCW
M25
2nd Spindle Stop
M30
End of program and reset
M98
Subprogram call
M99
Subprogram end
M198
External subprogram call
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/numeripath/
TITLE: NumeriPath
======================================================================
PDF
Simulation
Supported Controls
NumeriPath
NumeriPath
Subsections
NumeriPath Milling
NumeriPath Turning
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/numeripath/numeripath-milling/
TITLE: NumeriPath Milling
======================================================================
PDF
Simulation
Supported Controls
NumeriPath
NumeriPath Milling
NumeriPath Milling
List of G and M-codes for NumeriPath Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
AX plane selection
G21
BY plane selection
G22
CZ plane selection collinear Y
G23
CZ plane selection collinear X
G24
AB plane selection
G25
VW plane - NC contouring head
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G43
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G44
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G50
Adaptive control off
G51
Adaptive control on
G60
Cancel envelopes
G61
Enable envelope 1
G62
Enable envelope 2
G70
Input in inch
G71
Input in mm
G80
Canned cycle cancel
G81
Drill/Bore cycle
G82
Drill/Bore/Dwell cycle
G83
Deep hole drill cycle
G84
Tap cycle
G85
Feed in / Feed out cycle
G86
Bore / Stopped spindle retract cycle
G87
Chip breaker drill cycle
G88
Bore / Orient spindle / Move off center / Retract cycle
G89
Back bore cycle
G90
Absolute programming
G91
Incremental programming
G92
Work Coordinate Systems Shift Value
G94
Feed per minute
G95
Feed per revolution
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M8
Coolant ON – Flood coolant
M9
Coolant Off
M30
End of program and reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/numeripath/numeripath-turning/
TITLE: NumeriPath Turning
======================================================================
PDF
Simulation
Supported Controls
NumeriPath
NumeriPath Turning
NumeriPath Turning
List of G and M-codes for NumeriPath Turning as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
AX plane selection
G21
BY plane selection
G22
CZ plane selection collinear Y
G23
CZ plane selection collinear X
G24
AB plane selection
G25
VW plane - NC contouring head
G33
Thread cutting, constant lead
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G43
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G44
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G50
Adaptive control off
G51
Adaptive control on
G60
Cancel envelopes
G61
Enable envelope 1
G62
Enable envelope 2
G70
Input in inch
G71
Input in mm
G80
Canned cycle cancel
G81
Drill/Bore cycle
G82
Drill/Bore/Dwell cycle
G83
Deep hole drill cycle
G84
Tap cycle
G85
Feed in / Feed out cycle
G86
Bore / Stopped spindle retract cycle
G87
Chip breaker drill cycle
G88
Bore / Orient spindle / Move off center / Retract cycle
G89
Back bore cycle
G90
Absolute programming
G91
Incremental programming
G92
Work Coordinate Systems Shift Value
G94
Feed per minute
G95
Feed per revolution
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M8
Coolant ON – Flood coolant
M9
Coolant Off
M30
End of program and reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/okuma/
TITLE: Okuma
======================================================================
PDF
Simulation
Supported Controls
Okuma
Okuma
Subsections
Okuma Turning
Okuma Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/okuma/okuma-milling/
TITLE: Okuma Milling
======================================================================
PDF
Simulation
Supported Controls
Okuma
Okuma Milling
Okuma Milling
List of G and M-codes for Okuma Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Rapid interpolation
G1
Linear interpolation
G2
Circular interpolation - Helical cutting (CW)
G3
Circular interpolation - Helical cutting (CCW)
G4
Dwell
G10
Cancel of G11
G11
Parallel and rotational shift of coordinate system
G15
Selection of work coordinate system (Modal)
G16
Selection of work coordinate system (One-shot)
G17
Plane selection: XY
G18
Plane selection: ZX
G19
YZ Plane Selection
G20
Inch input confirmation
G21
Metric input confirmation
G30
Positioning to home position
G40
Cutter radius compensation (G41, G42) cancel
G41
Cutter radius compensation, left
G42
Cutter radius compensation, right
G53
Tool length offset cancel
G56
Tool length offset, Z-axis
G71
Designation of return level for M53
G73
Fixed cycle, High speed drilling cycle
G74
Fixed cycle, Reverse tapping cycle
G75
Fixed cycle, Step & pick cycle
G76
Fixed cycle, Fine boring
G79
Fixed cycle, Variable pitch cycle
G80
Fixed cycle, Modal cancel
G81
Fixed cycle, Spot boring
G82
Fixed cycle, Counter boring
G83
Fixed cycle, Deep hole drilling cycle
G84
Fixed cycle, Tapping cycle
G85
Fixed cycle, Boring cycle
G86
Fixed cycle, Boring cycle
G87
Fixed cycle, Back boring cycle
G88
Fixed cycle, Multi-step boring cycle
G89
Fixed cycle, Boring cycle
G90
Absolute dimensioning mode
G91
Incremental dimensioning mode
G94
Feed per minute mode
G95
Feed per revolution mode
G131
High-speed contouring control ON
G169
Tool length offset at cutting edge ON
G170
Tool length offset at cutting edge and in axial direction cancel
G272
Fixed cycle; Deep hole tapping and reverse tapping
G273
Fixed cycle; High-speed deep hole tapping and reverse tapping
G274
Fixed cycle; Synchronized tapping, reverse tapping
G281
Fixed cycle; Small diameter and deep hole drilling
G282
Fixed cycle; Deep hole synchronized tapping
G283
Fixed cycle; High-speed deep hole synchronized tapping
G284
Fixed cycle; Synchronized tapping
G604
Dynamic fixture offset mode OFF
G605
Dynamic fixture offset mode ON
M-Codes
Description
M0
Program stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M8
Coolant On
M9
Coolant Off
M15
4th axis CW rotation
M16
4th axis CCW rotation
M30
End of program and reset
M52
Return to upper limit level
M53
Return to specified point level
M54
Return to the point R level
M115
5th axis CW rotation
M116
5th axis CCW rotation
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/okuma/okuma-turning/
TITLE: Okuma Turning
======================================================================
PDF
Simulation
Supported Controls
Okuma
Okuma Turning
Okuma Turning
List of G and M-codes for Okuma Turning as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning
G1
Linear interpolation
G2
Circular interpolation - Helical cutting (CW)
G3
Circular interpolation - Helical cutting (CCW)
G4
Dwell
G15
Selection of work coordinate system (Modal)
G16
Selection of work coordinate system (One-shot)
G17
XY Plane Selection
G18
Plane selection: ZX
G19
YZ Plane Selection
G20
Home position return command
G31
Fixed Thread Cutting Cycle : longitudinal
G32
Fixed Thread Cutting Cycle: Transversal
G33
Fixed Thread Cutting Cycle : longitudinal
G34
Non-Fixed Thread Cutting Cycle : increasing
G35
Non-Fixed Thread Cutting Cycle : decreasing
G40
Cutter radius compensation (G41, G42) cancel
G41
Cutter radius compensation, left
G42
Cutter radius compensation, right
G50
Zero shift/Spindle Speed Maximum RPM Limit
G69
Longitudinal taper shape cutting cycle
G70
End face taper shape cutting cycle
G71
Longitudinal thread cutting cycle (compound/multiple pass)
G72
Transveral thread cutting cycle (compound/multiple pass)
G73
Longitudinal Grooving Fixed Cycle
G74
Transversal grooving/drilling fixed cycle
G75
Automatic C-chamfering
G76
Automatic rounding
G77
Right hand tapping cycle
G78
Left hand tapping cycle
G80
End of contour definition (LAP)
G81
Start of contour definition, longitudinal (LAP)
G82
Start of contour definition, transversal (LAP)
G83
Start of blank shape definition (LAP4 only)
G84
Change of rough turning conditions, bar turning (LAP)
G85
Bar turning cycle (LAP)
G86
Copy turning cycle (LAP)
G87
Finish turning cycle (LAP)
G90
Absolute dimensioning mode
G91
Incremental dimensioning mode
G94
Feed Per Minute Mode
G95
Feed Per Revolution
G96
Turns on constant surface speed
G97
Cancels constant surface speed
G101
Linear interpolation in contour generation
G102
Circular interpolation in contour generation (Face) (CW)
G103
Circular interpolation in contour generation (Face) (CWW)
G136
End of coordinate conversion or Y-axis mode OFF
G137
Start of coordinate conversion
G138
Y-axis mode ON
G178
Forward tapping cycle
G179
Reverse tapping cycle
G180
Cancel of Fixed Cycle
G181
Drilling Cycle
G182
Boring Cycle
G183
Deep hole Drilling Cycle
G184
Tapping cycle
G185
Longitudinal compound thread cutting cycle
G186
Transversal compound thread cutting cycle
G187
Longitudinal straight compound thread cutting cycle
G188
Transversal compound straight thread cutting cycle
G189
Reaming/Boring Cycle
M-Codes
Description
M0
Program stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M8
Coolant On
M9
Coolant Off
M12
M-tool Spindle Stop
M13
M-tool Spindle CW
M19
Orient Spindle
M22
Chamfering OFF
M23
Chamfering ON
M26
Cancellation of M27, parallel to Z-axis
M27
Parallel to X-axis ON
M30
End of program and reset
M32
Straight infeed along thread face (on left face)
M33
Zigzag infeed
M73
Infeed pattern 1
M74
Infeed pattern 2
M75
Demin. cuts even cross section
M83
Chuck clamp
M84
Chuck unclamp
M85
No return to the cutting starting point after the completion of rough turning cycle
M88
Air blower OFF
M89
Air blower ON
M248
Sub spindle chuck clamp
M249
Sub spindle chuck unclamp
M254
Program stop
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/osai/
TITLE: OSAI
======================================================================
PDF
Simulation
Supported Controls
OSAI
OSAI
Subsections
OSAI Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/osai/osai-milling/
TITLE: OSAI Milling
======================================================================
PDF
Simulation
Supported Controls
OSAI
OSAI Milling
OSAI Milling
List of G and M-codes for OSAI Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Positioning (rapid traverse)
G1
Linear interpolation (cutting feed)
G2
Circular interpolation CW or helical interpolation CW
G3
Circular interpolation CW or helical interpolation CCW
G4
Dwell
G16
Defined interpolation plane
G17
XY Plane Selection
G18
XZ Plane Selection
G19
YZ Plane Selection
G20
Closes GTL profile
G21
Opens GTL profile
G40
Tool radius/tool nose radius compensation : cancel, 3-dimensional cutter compensation : cancel
G41
Tool radius/tool nose radius compensation : left, 3-dimensional cutter compensation : left
G42
Tool radius/tool nose radius compensation : right, 3-dimensional cutter compensation : right
G70
Input in inch
G71
Input in mm
G72
Point Measurement with Compensation
G73
Hole probing with probe ball radius compensation
G74
Probing for theoretical deviation from point without probe ball radius compensation
G79
Programming referred to machine zero
G80
Disables fixed cycles
G81
Drilling Cycle
G82
Spot Facing Cycle
G83
Deep Drilling Cycle
G84
Tapping Cycle with Transducer
G85
Reaming Cycle (or Tapping by Tapmatic)
G86
Boring cycle
G89
Boring cycle with Spot Facing
G90
Absolute programming
G91
Incremental programming
G92
Work Coordinate Systems Shift Value
G94
Feed per minute
G95
Feed per revolution
G96
Constant surface speed in fpm or mpm
G97
Spindle speed programming in rpm
G99
Deletes G92
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Spindle CW
M4
Spindle CCW
M5
Spindle Stop
M6
Tool Change
M8
Coolant ON – Flood coolant
M9
Coolant Off
M13
Spindle ON clockwise/Coolant ON
M14
Spindle ON counterclockwise/Coolant ON
M19
Spindle Stop and Angular Orientation
M30
End of program and reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/roeders/
TITLE: Roeders
======================================================================
PDF
Simulation
Supported Controls
Roeders
Roeders
Subsections
Roeders Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/roeders/roeders-milling/
TITLE: Roeders Milling
======================================================================
PDF
Simulation
Supported Controls
Roeders
Roeders Milling
Roeders Milling
List of G and M-codes for Roeders Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Linear interpolation in rapid feed
G1
Linear interpolation with feed specification
G2
Circular Interpolation Motion CW
G3
Circular Interpolation Motion CCW
G17
Plane selection XY
G18
Plane selection ZX
G19
Plane selection YZ
G40
Deactivating radius correction
G41
2D radius correction to the left of the contour
G42
2D radius correction to the right of the contour
G70
Dimensions specified in inches
G71
Dimensions specified in millimeters
G90
Absolute dimensions
G91
Incremental dimensions
M-Codes
Description
M3
Spindle CW
M5
Spindle Stop
M8
Turn spray cooling on
M9
Turn spray cooling off
M30
End of program
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/siemens/
TITLE: Siemens
======================================================================
PDF
Simulation
Supported Controls
Siemens
Siemens
Subsections
Siemens Turning
Siemens Milling
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/siemens/siemens-milling/
TITLE: Siemens Milling
======================================================================
PDF
Simulation
Supported Controls
Siemens
Siemens Milling
Siemens Milling
List of G and M-codes for Siemens Milling as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Command for the activation of rapid traverse motion
G1
Command for the activation of linear interpolation
G2
Command for the activation of clockwise circular interpolation
G3
Command for the activation of counter-clockwise circular interpolation
G4
Dwell
G17
Working plane X/Y
G18
Working plane Z/X
G19
Working plane Y/Z
G25
Lower spindle speed limit
G26
Upper spindle speed limit
G40
Tool radius compensation deactivation
G41
Tool radius compensation left
G42
Tool radius compensation right
G53
G53 suppresses the settable zero offset and the programmable zero offset non-modally
G54
Call of the 1st settable zero offset
G55
Call of the 2nd settable zero offset
G56
Call of the 3rd settable zero offset
G57
Call of the 4th settable zero offset
G58
Absolute programmable work offset
G59
Additive programmable work offset
G70
Activation of the inch measuring system
G71
Activation of the metric measuring system
G74
Search for reference
G75
Fixed point approach
G90
Command for the activation of modal absolute dimensions
G91
Command for the activation of modal incremental dimensions
G94
Path feed type: Linear feedrate [mm/min], [inch/min] or [degrees/min]
G95
Path feed type: Revolutional feedrate [mm/revolution] or [inch/revolution]
G96
Constant cutting rate with feedrate type G95: ON
G97
Deactivate constant cutting rate with feedrate type G95
G110
Pole programming relative to the last programmed setpoint position
G111
Pole programming relative to zero of current workpiece coordinate system
G112
Pole programming relative to the last valid pole
G153
G153 has the same effect as G53 and also suppresses the entire basic frame
G450
Transition circle, radius compensation corner behaviour
G451
Intersection of equidistances, radius compensation corner behaviour
G500
Deactivation of the current settable zero offset
G505
Call of the 5th settable zero offset
G506
Call of the 6th settable zero offset
G507
Call of the 7th settable zero offset
G508
Call of the 8th settable zero offset
G509
Call of the 9th settable zero offset
G510
Call of the 10th settable zero offset
G511
Call of the 11th settable zero offset
G512
Call of the 12th settable zero offset
G513
Call of the 13th settable zero offset
G514
Call of the 14th settable zero offset
G515
Call of the 15th settable zero offset
G516
Call of the 16th settable zero offset
G517
Call of the 17th settable zero offset
G518
Call of the 18th settable zero offset
G519
Call of the 19th settable zero offset
G520
Call of the 20th settable zero offset
G521
Call of the 21th settable zero offset
G522
Call of the 22th settable zero offset
G523
Call of the 23th settable zero offset
G524
Call of the 24th settable zero offset
G525
Call of the 25th settable zero offset
G526
Call of the 26th settable zero offset
G527
Call of the 27th settable zero offset
G528
Call of the 28th settable zero offset
G529
Call of the 29th settable zero offset
G530
Call of the 30th settable zero offset
G531
Call of the 31th settable zero offset
G532
Call of the 32th settable zero offset
G533
Call of the 33th settable zero offset
G534
Call of the 34th settable zero offset
G535
Call of the 35th settable zero offset
G536
Call of the 36th settable zero offset
G537
Call of the 37th settable zero offset
G538
Call of the 38th settable zero offset
G539
Call of the 39th settable zero offset
G540
Call of the 40th settable zero offset
G541
Call of the 41th settable zero offset
G542
Call of the 42th settable zero offset
G543
Call of the 43th settable zero offset
G544
Call of the 44th settable zero offset
G545
Call of the 45th settable zero offset
G546
Call of the 46th settable zero offset
G547
Call of the 47th settable zero offset
G548
Call of the 48th settable zero offset
G549
Call of the 49th settable zero offset
G550
Call of the 50th settable zero offset
G551
Call of the 51th settable zero offset
G552
Call of the 52th settable zero offset
G553
Call of the 53th settable zero offset
G554
Call of the 54th settable zero offset
G555
Call of the 55th settable zero offset
G556
Call of the 56th settable zero offset
G557
Call of the 57th settable zero offset
G558
Call of the 58th settable zero offset
G559
Call of the 59th settable zero offset
G560
Call of the 60th settable zero offset
G561
Call of the 61th settable zero offset
G562
Call of the 62th settable zero offset
G563
Call of the 63th settable zero offset
G564
Call of the 64th settable zero offset
G565
Call of the 65th settable zero offset
G566
Call of the 66th settable zero offset
G567
Call of the 67th settable zero offset
G568
Call of the 68th settable zero offset
G569
Call of the 69th settable zero offset
G570
Call of the 70th settable zero offset
G571
Call of the 71th settable zero offset
G572
Call of the 72th settable zero offset
G573
Call of the 73th settable zero offset
G574
Call of the 74th settable zero offset
G575
Call of the 75th settable zero offset
G576
Call of the 76th settable zero offset
G577
Call of the 77th settable zero offset
G578
Call of the 78th settable zero offset
G579
Call of the 79th settable zero offset
G580
Call of the 80th settable zero offset
G581
Call of the 81th settable zero offset
G582
Call of the 82th settable zero offset
G583
Call of the 83th settable zero offset
G584
Call of the 84th settable zero offset
G585
Call of the 85th settable zero offset
G586
Call of the 86th settable zero offset
G587
Call of the 87th settable zero offset
G588
Call of the 88th settable zero offset
G589
Call of the 89th settable zero offset
G590
Call of the 90th settable zero offset
G591
Call of the 91th settable zero offset
G592
Call of the 92th settable zero offset
G593
Call of the 93th settable zero offset
G594
Call of the 94th settable zero offset
G595
Call of the 95th settable zero offset
G596
Call of the 96th settable zero offset
G597
Call of the 97th settable zero offset
G598
Call of the 98th settable zero offset
G599
Call of the 99th settable zero offset
G700
Activation of the inch measuring system
G710
Activation of the metric measuring system
G961
Constant cutting rate with feedrate type G94: ON
G962
Constant cutting rate with feedrate type G94 or G95: ON
G971
Deactivate constant cutting rate with feedrate type G94
G972
Deactivate constant cutting rate with feedrate type G94 or G95
G973
Deactivate constant cutting rate without activating spindle speed limitation
M-Codes
Description
M0
Programmed stop
M1
Optional stop
M2
End of program
M3
Direction of spindle rotation clockwise for master spindle
M4
Direction of spindle rotation counter-clockwise for master spindle
M5
Spindle stop for master spindle
M6
Tool Change
M17
Subprogram end
M30
End of program and reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/supported-controls/siemens/siemens-turning/
TITLE: Siemens Turning
======================================================================
PDF
Simulation
Supported Controls
Siemens
Siemens Turning
Siemens Turning
List of G and M-codes for Siemens Turning as of CIMCO Edit 2026.01.09
G-Codes
Description
G0
Command for the activation of rapid traverse motion
G1
Command for the activation of linear interpolation
G2
Command for the activation of clockwise circular interpolation
G3
Command for the activation of counter-clockwise circular interpolation
G4
Dwell
G17
Working plane X/Y
G18
Working plane Z/X
G19
Working plane Y/Z
G25
Lower spindle speed limit
G26
Upper spindle speed limit
G33
Thread cutting with constant lead
G40
Tool nose compensation cancel
G41
Tool radius compensation left
G42
Tool radius compensation right
G53
Machine coordinate system setting
G54
Call of the 1st settable zero offset
G55
Call of the 2nd settable zero offset
G56
Call of the 3rd settable zero offset
G57
Call of the 4th settable zero offset
G58
Absolute programmable work offset
G59
Additive programmable work offset
G63
Tapping with compensating chuck
G70
Activation of the inch measuring system
G71
Activation of the metric measuring system
G74
Search for reference
G75
Fixed point approach
G90
Command for the activation of modal absolute dimensions
G91
Command for the activation of modal incremental dimensions
G93
Path feed type: Inverse-time feedrate [rpm]
G94
Path feed type: Linear feedrate [mm/min], [inch/min] or [degrees/min]
G95
Path feed type: Revolutional feedrate [mm/revolution] or [inch/revolution]
G96
Constant cutting rate with feedrate type G95: ON
G97
Deactivate constant cutting rate with feedrate type G95
G153
Machine coordinate system setting
G450
Transition circle, radius compensation corner behaviour
G451
Intersection of equidistances, radius compensation corner behaviour
G500
Deactivation of the current settable zero offset
G505
Call of the 5th settable zero offset
G506
Call of the 6th settable zero offset
G507
Call of the 7th settable zero offset
G508
Call of the 8th settable zero offset
G509
Call of the 9th settable zero offset
G510
Call of the 10th settable zero offset
G511
Call of the 11th settable zero offset
G512
Call of the 12th settable zero offset
G513
Call of the 13th settable zero offset
G514
Call of the 14th settable zero offset
G515
Call of the 15th settable zero offset
G516
Call of the 16th settable zero offset
G517
Call of the 17th settable zero offset
G518
Call of the 18th settable zero offset
G519
Call of the 19th settable zero offset
G520
Call of the 20th settable zero offset
G521
Call of the 21th settable zero offset
G522
Call of the 22th settable zero offset
G523
Call of the 23th settable zero offset
G524
Call of the 24th settable zero offset
G525
Call of the 25th settable zero offset
G526
Call of the 26th settable zero offset
G527
Call of the 27th settable zero offset
G528
Call of the 28th settable zero offset
G529
Call of the 29th settable zero offset
G530
Call of the 30th settable zero offset
G531
Call of the 31th settable zero offset
G532
Call of the 32th settable zero offset
G533
Call of the 33th settable zero offset
G534
Call of the 34th settable zero offset
G535
Call of the 35th settable zero offset
G536
Call of the 36th settable zero offset
G537
Call of the 37th settable zero offset
G538
Call of the 38th settable zero offset
G539
Call of the 39th settable zero offset
G540
Call of the 40th settable zero offset
G541
Call of the 41th settable zero offset
G542
Call of the 42th settable zero offset
G543
Call of the 43th settable zero offset
G544
Call of the 44th settable zero offset
G545
Call of the 45th settable zero offset
G546
Call of the 46th settable zero offset
G547
Call of the 47th settable zero offset
G548
Call of the 48th settable zero offset
G549
Call of the 49th settable zero offset
G550
Call of the 50th settable zero offset
G551
Call of the 51th settable zero offset
G552
Call of the 52th settable zero offset
G553
Call of the 53th settable zero offset
G554
Call of the 54th settable zero offset
G555
Call of the 55th settable zero offset
G556
Call of the 56th settable zero offset
G557
Call of the 57th settable zero offset
G558
Call of the 58th settable zero offset
G559
Call of the 59th settable zero offset
G560
Call of the 60th settable zero offset
G561
Call of the 61th settable zero offset
G562
Call of the 62th settable zero offset
G563
Call of the 63th settable zero offset
G564
Call of the 64th settable zero offset
G565
Call of the 65th settable zero offset
G566
Call of the 66th settable zero offset
G567
Call of the 67th settable zero offset
G568
Call of the 68th settable zero offset
G569
Call of the 69th settable zero offset
G570
Call of the 70th settable zero offset
G571
Call of the 71th settable zero offset
G572
Call of the 72th settable zero offset
G573
Call of the 73th settable zero offset
G574
Call of the 74th settable zero offset
G575
Call of the 75th settable zero offset
G576
Call of the 76th settable zero offset
G577
Call of the 77th settable zero offset
G578
Call of the 78th settable zero offset
G579
Call of the 79th settable zero offset
G580
Call of the 80th settable zero offset
G581
Call of the 81th settable zero offset
G582
Call of the 82th settable zero offset
G583
Call of the 83th settable zero offset
G584
Call of the 84th settable zero offset
G585
Call of the 85th settable zero offset
G586
Call of the 86th settable zero offset
G587
Call of the 87th settable zero offset
G588
Call of the 88th settable zero offset
G589
Call of the 89th settable zero offset
G590
Call of the 90th settable zero offset
G591
Call of the 91th settable zero offset
G592
Call of the 92th settable zero offset
G593
Call of the 93th settable zero offset
G594
Call of the 94th settable zero offset
G595
Call of the 95th settable zero offset
G596
Call of the 96th settable zero offset
G597
Call of the 97th settable zero offset
G598
Call of the 98th settable zero offset
G599
Call of the 99th settable zero offset
G700
Activation of the inch measuring system
G710
Activation of the metric measuring system
G961
Constant cutting rate with feedrate type G94: ON
G962
Constant cutting rate with feedrate type G94 or G95: ON
G971
Deactivate constant cutting rate with feedrate type G94
G972
Deactivate constant cutting rate with feedrate type G94 or G95
G973
Deactivate constant cutting rate without activating spindle speed limitation
M-Codes
Description
M0
Programmed stop
M1
Optional stop or spindle settings
M2
End of program or spindle settings
M3
Direction of spindle rotation clockwise for master spindle
M4
Direction of spindle rotation counter-clockwise for master spindle
M5
Spindle stop for master spindle
M6
Tool Change
M17
Subprogram end
M30
End of program and reset
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/tool-manager/
TITLE: Tool Manager
======================================================================
PDF
Simulation
Tool Manager
Tool Manager
This section describes the Tool Manager which is used for creating and editing tools, and setting up tool libraries.
Subsections
Edit Assembly
Edit Cutter
Edit Holder
The Tool Manager is opened in the following way:
Select the
Backplot tab
Find the
Tools menu
and click the option
Tool Setup
The main window in the Tool Manager is divided into three areas:
Tools in current NC program:
The upper area contains the tools identified in the current NC program (marked with red in the screenshot below).
Tool Libraries:
The lower area contains tool libraries (marked with blue below).
Tool Preview:
The section on the right contains a preview of the tool currently selected (marked Green below).
The elements and options in each of these areas are described below.
Tool Manager.
Tools in current NC program
Tabs (Assemblies, Cutters and Holders)
Select these tabs to see a list of the assemblies, cutters and holders identified in the current NC program.
Click an item to select it (notice the Edit and Delete options on the right)
Double-click an item to edit it
Right-click an item for additional options (see below)
Please see the following sections for information about how to edit an Assembly, Cutter or Holder:
Editing an Assembly
Editing a Cutter
Editing a Holder
Right-click menu
Edit
: Edit the selected item
Duplicate
: Duplicate the selected item
Delete
: Delete the selected item
Item id
: Add a custom id to the item
Item number
: The number of the item within the NC program
Description
: A description of the item
Add Item to Current Document
Create a tool assembly or an individual tool component such as a holder, a drilling tool, a milling tool, insert, etc. to the current NC program.
Please refer to
Create Item
for more information.
Hide Preview
Select this option to hide the tool preview section.
Delete Associated Components
Enable this option to also delete associated components such as
holder
and
cutter
when deleting an assembly.
Tool Libraries
Visibility options
Select this menu to hide the entire Tool Libraries section or just the libraries on the left.
Libraries
Displays a list of predefined and custom tool libraries.
Click a library to select it
Right-click a library to rename or delete it
Hover the mouse over a library to see where it is located in the file system. Libraries are always stored under /ToolLibs in the install folder.
When a library is selected, these options are also available as icons on the right side of the selection.
Tabs (Assemblies, Cutters and Holders)
Select these tabs to see a list of the assemblies, cutters and holders available in the currently selected library.
Click an item to select it (notice the Edit and Delete options on the right)
Double-click an item to edit it
Right-click an item for additional options (see below)
Please see the following sections for information about how to edit an Assembly, Cutter or Holder:
Editing an Assembly
Editing a Cutter
Editing a Holder
Right-click menu
Edit
: Edit the selected item
Duplicate
: Duplicate the selected item
Delete
: Delete the selected item
Item id
: Add a custom id to the item
Item number
: The number of the item within the NC program
Description
: A description of the item
Errors
If the Tool Manger detects and error, the item will show a red triangle
on the right side of the list. Hover the mouse over the triangle to see a description of the error.
Copy
Tools can be copied between a library and the current tool list. The copy button's directional arrow (up or down) will toggle based on the selection made in either the upper list or a library.
Replace
A tool from the library can replace a tool selected in the current list, preserving the original tool number. A tool from the current list can also replace a tool in a library. The direction of the replace button's arrow (up or down) will toggle based on the selection made in either the upper list or a library.
Create Library or Add Item
Select this to create a new library or add a tool assembly or an individual tool component such as a holder, a drilling tool, a milling tool, insert, etc to a library.
Please refer to
Create Item
for more information.
Tool Preview
Toggle Dark Mode Rendering
Select this item to toggle between dark and light rendering of the tool preview section.
Create Item
The
Create item
dialog appears when creating an assembly, cutter, holder, component, or library.
The dialog is dynamic and will change depending on the type of item you are creating. Some items have several subgroups to help you select the exact item you require. Once selected, the Tool Manager will continue to let you configure the item.
Save and Close
When the simulation (either Backplot or Machine Simulation) is running, CIMCO Edit retains the tool configuration settings (for tools in the current NC program), and any changes made in the Tool Manager will be instantly reflected in the simulation. However, if you close (end) the Backplot or Machine Simulation without saving, these modifications will be lost.
To save changes made in the Tool Manager, follow these steps:
Close the Tool Manager (if open)
Right-click anywhere in the
Geometry Manager
Select the option
Save Setup
(see below)
Close
Select the X to close the Tool Manager. The simulation will update to reflect your changes.
Save (Save Setup)
By default, the tool configuration associated with the current NC program will automatically be saved to a .setup file located in the same folder as the NC program file. However, it is also possible to write (insert) the configuration directly into the active NC program itself.
The method of saving depends on how
Scanning
is configured within CIMCO Edit. Both setup and tool configuration data are saved using
Scanning Commands
which are automatically loaded when starting simulation.
Please refer to the
Scanning
section in the Editor Setup for more information.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/tool-manager/edit-assembly/
TITLE: Editing an Assembly
======================================================================
PDF
Simulation
Tool Manager
Edit Assembly
Editing an Assembly
The
Editing assembly
window allows for the configuration of both the cutter and the holder, which constitute the components of an assembly.
Please see
Tool Manager
for information on how to select an assembly and open the
Editing assembly
window.
Editing assembly window.
The sidebar on the left contains two tabs; the
Design
and the
Details
tab.
The
Save
,
Save as
and
Cancel
buttons are at the bottom of the sidebar.
Save as
saves the changes as a new item. You can also use the Escape key to Cancel and return to the previous window.
Design tab
The
Design
tab contains the components that constitute the assembly. The components are nested such that a holder contains a cutter.
Hover the mouse over a component to highlight it in the assembly preview on the right.
Click the left mouse button to select the component
Double-click a component to edit it
You can also do this directly on the assembly preview.
Edit Component
Select this option to edit the component.
Select Component (Replace)
Select this option to replace the component with another.
Remove Component
Select this option to remove the component. Any nested components will be removed as well.
Create New Component
When creating an empty assembly or if a component has been removed, select this option to add a new component.
Details tab
The
Details
tab contains information about the assembly such as a Description, ID and Item number. This information is also shown in the current list and library.
An assembly also allows you to set the
Cutter point
and
Orientation
depending on the machine setup.
Description
Add a description of the item.
ID
Add a custom id to the item.
Item number
The number of the item within the NC program.
Radius compensation value
The radius used for cutter radius compensation. It is taken from the cutter: half its diameter offset when the cutter uses a diameter offset, otherwise its radius compensation.
Cutter point (Milling)
The
Cutter point
refers to the actual cutting edge of the tool that engages with the material. It is the part of the tool that performs the cutting action.
Center compensation point:
Adjusts the toolpath for the center of the tool. Useful for tools that do not have a symmetrical cutting profile or when the exact center is crucial for the machining.
Tip compensation point:
Adjusts the toolpath to account for the exact point of the tool that is doing the cutting, which is especially important for tools with a defined tip, such as drills or engraving tools.
Cutter point (Turning)
The Cutter point refers to the actual cutting edge of the tool that engages with the material. It is the sharp edge of the insert that comes into direct contact with the material to be cut.
The options T2, T6, T1, T0/T9, etc. allows you to define the position of the cutting point.
Cutter point shift
Only shown for grooving and parting tools. Moves the cutter point along X by the value entered. The default is 0, which keeps the cutter point given by the insert.
Orientation
Use this to set the orientation of the tool assembly.
Add advanced tool location
Click this button to set up a tool that is not in line with the spindle, for example a tool in an angle head or a turret mount. The button shows the
Tool location X / Y / Z
,
Orientation
and
Machine View Angle
settings, and the
Mount Filename
field once a tool location is set. The button is hidden when these settings are already in use.
Tool location X / Y / Z
The position of the tool tip relative to the tool mount. Use this for tools that are not in line with the spindle, for example in an angle head or a turret mount. The fields are available for milling and turning tools. The tool location is also used for a tool that points straight down but is offset from the spindle, for example on an extender.
Station number
Only shown for turning and mill-turn machines, after you click
Add advanced tool location
. Sets the turret station that the tool is mounted in during simulation. The station number follows the
Item number
until you give it a different value.
Mount Filename
The STL or .tooldata file of the tool mount, for example a turret holder or an angle head. Click the browse button to select the file. The field is shown when a tool location is set, and shows an error when the file does not exist or has another format.
Machine View Angle
Use the arrow buttons to turn the tool around the spindle axis of the angle head. For lathe tools the setting is called
Approach Direction
. The setting is disabled when
Orientation
is 0 or 180.
Color
Click the color field and pick a color for the tool. The simulation shows the tool in this color. If no color is picked, the tool is shown in the normal tool color.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/tool-manager/edit-cutter/
TITLE: Editing a Cutter
======================================================================
PDF
Simulation
Tool Manager
Edit Cutter
Editing a Cutter
The
Editing cutter
window allows you to define a cutter.
Please see
Tool Manager
for information on how to select a cutter and open the
Editing cutter
window.
The term 'Cutter' broadly refers to any component that interacts with the material being worked on. This includes milling tools, turning inserts, and even probes. It is used in the Tool Manager as a general term for the part of the assembly that makes contact with the workpiece.
Editing a Cutter (milling tool left, turning insert right).
Workflow
As you move the cursor over the different segments of the cutter, the corresponding parameter fields will be highlighted with a blue border. Milling tools normally consists of multiple segments while turning inserts have a single segment.
To select a segment, simply click on it. This will also highlight and activate the related parameter field. You can then directly click on the segment, input your desired value, and press enter to apply the change.
Repeatedly clicking on a segment will cycle through the related parameters, and the measurements will be displayed within the preview for easy reference.
For milling tools and probes, the
Body length
is the total length of the cutter, from the tip to the end where it is held in place. Within this total length, you decide the
Taper length
and
Shoulder length
. Finally, within the Shoulder, you define the
Flute length
. So, you are setting the lengths of each distinct section of the milling tool, starting from the overall tool down to the cutting area.
Every cutter type comes with its own set of options and parameters. Each parameter has a clear description and by using the method above of selecting and cycling through the parameters, it should be both intuitive and straightforward to configure a cutter.
Design tab
Measurement units
Select the unit of measurement you prefer.
The following parameters are some of the more common ones for milling tools, however, parameters will vary depending on the specific cutter selected.
Flute diameter
The diameter of the working part of the tool where the flutes are located.
Flute length
The Flute length defines how far the flutes go along the body of the tool.
Body length
The total length of the tool including the taper, shoulder and flutes segments.
Shoulder diameter
The diameter of the shoulder.
Shoulder length
The length of the shoulder which also includes the flutes segment.
Shaft diameter
The diameter of the shaft, which is the part of the tool that is held by the tool holder.
Taper length
The length of the tapered section of the tool.
Corner radius
The radius of the tool's tip within the flutes segment.
Chamfer distance
The length of the chamfered edge at the tool's tip within the flutes segment.
Details tab
Description
Add a description of the item.
ID
Add a custom id to the item.
Filename
Use this field to display an STL model in the simulation instead of the configured cutter.
Click the folder icon to locate an STL file
The file's path will automatically be inserted in the field
The STL model will only show in the simulation once an STL has been selected for all components in an assembly (for both the holder and cutter).
This feature is intended for visual purposes only. CIMCO Edit will continue to rely on the configured cutter for internal operations like collision detection.
Assembly number
Shows the Assembly item number or the text
Multiple
if the holder is used in more than one assembly.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/tool-manager/edit-holder/
TITLE: Editing a Holder
======================================================================
PDF
Simulation
Tool Manager
Edit Holder
Editing a Holder
The
Editing holder
window allows you to define a holder.
Please see
Tool Manager
for information on how to select a holder and open the
Editing holder
window.
Editing a Holder (milling holder left, turning holder right).
Workflow
As you move the cursor over the different segments of the holder, the corresponding
Holder Segment
field (milling) or
Parameter Field(s)
(turning) will be highlighted with a blue border.
To select a segment, simply click on it. This will also highlight and activate the related parameter field. You can then directly click on the segment, input your desired value, and press enter to apply the change.
Repeatedly clicking on a segment will cycle through the related parameters, and the measurements will be displayed within the preview for easy reference.
Milling holders consist of a sequence of holder segments that all have an Upper, Lower and Length parameter. Turning holders, on the other hand, offer a different set of choices and parameters that change based on the type you choose. Every parameter has a clear description and by using the method above of selecting and cycling through the parameters, it should be both intuitive and straightforward to configure a holder.
Design tab (Milling holder)
Measurement units
Select the unit of measurement you prefer.
Add New Holder Segment
Select this item to add a new holder segment to the bottom of the list.
Delete all Holder Segments
Select this item to delete all of the current holder segments.
Holder Segment
A holder consists of a sequence of holder segments which make up the full shape. Each segment is defined by the following measurements in either millimeters or inches:
Upper:
The width of the top edge
Lower:
The width of the bottom edge
Length:
The length of the segment from top to bottom
The measurements for the Upper and Lower widths are taken equidistantly from the holder's central axis. For instance, a 60mm width would extend 30mm to the left and 30mm to the right from the midpoint.
Up/down arrows:
Use the up/down arrows on the left to move the segment up or down in the list
Close icon:
Select this to remove the segment from the list
Design tab (Turning/Lathe holder)
Measurement units
Select the unit of measurement you prefer.
Parameter fields
Each type of turning holder has its own set of options and parameters. Parameters are distinctly labeled, and when you select one, the holder preview will visually indicate the part of the holder it corresponds to.
Gagepoint
Only for custom lathe holders. The gage point is the reference point of the holder.
Auto:
the gage point is set automatically (default).
Custom position:
enter the X, Y and Z position of the gage point.
Details tab
Description
Add a description of the item.
ID
Add a custom id to the item.
Filename
Use this field to display an STL model in the simulation instead of the configured holder.
Click the folder icon to locate an STL file
The file's path will automatically be inserted in the field
The STL model will only show in the simulation once an STL has been selected for all components in an assembly (for both the holder and cutter).
This feature is intended for visual purposes only. CIMCO Edit will continue to rely on the configured holder for internal operations like collision detection.
Assembly number
Shows the Assembly item number or the text
Multiple
if the holder is used in more than one assembly.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.

======================================================================
SOURCE_URL: https://docs.cimco.com/en/docs/edit/2026/simulation/variables/
TITLE: Variables Tab
======================================================================
PDF
Simulation
Variables Tab
Variables Tab
This section describes the
Variables
tab which is located in the docking pane.
The Variables tab is divided into two areas: the upper section displays the initial state of variables in your NC program, while the lower section, also referred to as the 'Watch List', shows the current state of variables at any point in the program.
Variables are automatically detected within the active NC program.
You can change the initial values in the upper section without changing the actual NC code. This provides a quick way to test different values. Simply click on a value to change it.
Variables tab.
Options
Filter by used variables
Enable this to only show the variables that are being used within the current NC program.
Copyright © CIMCO A/S | CIMCO Americas, LLC. All rights reserved.