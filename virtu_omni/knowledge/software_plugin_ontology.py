"""Industrial CAD/CAM/CAE Software & Plugin Exhaustive Ontology Knowledge Base.

Defines the complete structural hierarchy, menu architectures, command tokens,
API interfaces, official plugins/add-ins, and manufacturing semantics for:
1. SOLIDWORKS 2021
2. Siemens NX 12.0
3. AutoCAD 2026
4. Vericut 9.6
5. CIMCO Edit 2026
6. 斯沃数控仿真软件 (SSCNC 7.2)
"""

from typing import Any, Dict, List

SOFTWARE_ONTOLOGY: Dict[str, Dict[str, Any]] = {
    "SOLIDWORKS 2021": {
        "vendor": "Dassault Systèmes",
        "api_types": ["VBA Macro (.vbs / .swp)", "C# .NET API", "C++ COM API"],
        "core_features": {
            "sketching": ["Sketch2D", "Sketch3D", "SmartDimension", "AddRelation", "ConvertEntities", "OffsetEntities"],
            "solid_modeling": [
                "FeatureExtrusion2", "FeatureRevolve2", "FeatureSweep3", "FeatureLoft2",
                "FeatureBoundary2", "FeatureFillet3", "FeatureChamfer", "FeatureRib", "InsertShell", "InsertDraft"
            ],
            "surface_modeling": [
                "InsertOffsetSurface", "InsertRuledSurface", "InsertKnitSurface", "InsertTrimSurface",
                "InsertFillSurface", "InsertExtendSurface", "InsertBoundarySurface"
            ],
            "assembly": [
                "AddMate5", "InsertNewPart", "EditPart", "CreateComponentPattern",
                "MateTypes: Coincident, Concentric, Distance, Angle, Tangent, ProfileCenter, Slot, Cam, Gear, RackPinion"
            ],
            "mold_tools": [
                "DraftAnalysis", "UndercutAnalysis", "PartingLines", "ShutOffSurfaces",
                "PartingSurfaces", "ToolingSplit", "CoreAndCavitySurfaces"
            ],
            "sheet_metal": [
                "InsertBaseFlange", "InsertEdgeFlange", "InsertMiterFlange", "InsertHem",
                "InsertLoftedBend", "Unfold", "Fold", "ProcessBends"
            ],
            "equations": ["EquationMgr", "AddEquation", "GetEquationValue", "EvaluateEquation2"]
        },
        "plugins_and_addins": {
            "SOLIDWORKS Simulation (COSMOSWorks)": {
                "type": "CAE / Finite Element Analysis",
                "capabilities": ["Linear Static", "Frequency/Modal", "Buckling", "Thermal Transfer", "Drop Test", "Fatigue", "Nonlinear Stress"],
                "api_interfaces": ["CWModelDoc", "CWStudyManager", "CWStudy", "CWSolidManager", "CWMesh", "CWLoadsAndRestraints"],
                "boundary_conditions": ["Fixed Geometry", "Roller/Slider", "Elastic Support", "Bearing Load", "Centrifugal Load", "Pressure", "Thermal Convection"]
            },
            "SOLIDWORKS Motion (COSMOSMotion)": {
                "type": "Kinematic & Multi-Body Dynamic Simulation",
                "capabilities": ["Rigid Body Dynamics", "Contact Forces", "Gravity", "Springs", "Dampers", "Rotary/Linear Motors", "Path Motion", "Dynamic Torque Analysis"],
                "api_interfaces": ["CosmosMotionServer", "MotionStudy", "SimulationMotor", "ContactGroup"]
            },
            "SOLIDWORKS Flow Simulation": {
                "type": "Computational Fluid Dynamics (CFD)",
                "capabilities": ["Internal/External Flow", "Conjugate Heat Transfer", "Compressible Gas", "Non-Newtonian Liquids", "Rotating Frames", "Porosity"],
                "key_parameters": ["Computational Domain", "Subsonic/Supersonic Boundary", "Turbulence Model (k-epsilon)", "Surface Goals", "Volume Goals"]
            },
            "SOLIDWORKS Plastics": {
                "type": "Injection Molding CAE",
                "capabilities": ["Cavity Filling", "Packing Pressure", "Fiber Orientation", "Cooling Circuit Optimization", "Sink Mark Prediction", "Volumetric Warpage"],
                "key_parameters": ["Injection Gate Location", "Melt Temperature", "Mold Wall Temperature", "Clamp Force", "Cycle Time"]
            },
            "SOLIDWORKS CAM / CAMWorks": {
                "type": "Intelligent CNC Programming",
                "capabilities": ["Automatic Feature Recognition (AFR)", "Interactive Feature Recognition (IFR)", "TechDB Rule Engine", "2.5D Milling", "Multi-Axis Turning", "Toolpath Post-Processing"],
                "key_parameters": ["Stock Definition", "Part Setup Origin", "Machinable Feature Tree", "Operation Plan Generation"]
            },
            "Toolbox": {
                "type": "Standard Industrial Component Library",
                "standards": ["ISO", "GB", "DIN", "ANSI Metric/Inch", "JIS"],
                "components": ["Hex Bolts", "Socket Screws", "Nuts", "Washers", "Deep Groove Ball Bearings", "Spur/Bevel Gears", "O-Rings", "Pins"]
            },
            "Routing (Piping, Tubing, Electrical)": {
                "type": "Industrial Harness and Piping Design",
                "capabilities": ["Parametric Pipe Runs", "Flexible Hose Routing", "Wire Bundles", "Terminal Pinouts", "Cable Tray Layout"]
            }
        }
    },

    "中文版NX12.0": {
        "vendor": "Siemens PLM Software",
        "api_types": ["NXOpen Python", "NXOpen C++", "NXOpen .NET", "Classic User Function (UF) C API"],
        "core_features": {
            "synchronous_technology": ["MoveFace", "PullFace", "OffsetRegion", "ReplaceFace", "ResizeBlend", "CrossSectionEdit", "MakeCoplanar"],
            "freeform_surfacing": ["ThroughCurves", "ThroughCurveMesh", "StudioSurface", "SectionSurface", "GlobalShaping", "StyledBlend", "BridgeCurve"],
            "feature_modeling": ["CreateExtrude", "CreateRevolve", "CreateSweep", "CreateCylinder", "CreateBlock", "CreateTorus", "CreateSphere", "BooleanOperation"],
            "expressions_and_rules": ["ExpressionCollection", "CreateWithUnits", "InterPartExpression", "KnowledgeFusion", "ProductTemplateStudio (PTS)"],
            "convergent_modeling": ["FacetBody", "ConvergentBoolean", "MeshMorphing", "GenerativeDesignTopology"]
        },
        "plugins_and_addins": {
            "NX CAM (Manufacturing)": {
                "type": "High-End Multiaxis CNC Machining",
                "modules": ["Cavity Mill", "Z-Level Milling", "Contour Area", "Streamline", "Variable Guiding Curves (5-Axis)", "Rotary Floor", "Multi-Blade Impeller/Blisk", "Turn-Mill"],
                "api_interfaces": ["NXOpen.CAM.Operation", "NXOpen.CAM.CAMSetup", "NXOpen.UF.UFCam", "NXOpen.CAM.NCGroupCollection"],
                "post_processing": ["Post Builder", "Post Configurator", "MOM (Manufacturing Output Manager) Event Generator", "ISV (Machine Tool Simulation with G-Code)"]
            },
            "NX CAE / Simcenter 3D (Pre/Post)": {
                "type": "Multiphysics Engineering Simulation",
                "solvers": ["NX Nastran (Sol 101 Linear Statics, Sol 103 Normal Modes, Sol 105 Buckling, Sol 106 Nonlinear)", "NX Thermal/Flow", "NX Electronic Systems Cooling"],
                "api_interfaces": ["NXOpen.CAE.CaeSession", "NXOpen.CAE.MeshManager", "NXOpen.CAE.SimSimulation", "NXOpen.CAE.ResultManager"],
                "meshing": ["3D Tetrahedral 10-Node", "3D Hexahedral 8/20-Node", "2D Shell CQUAD4/CTRIA3", "1D Beam CBEAM"]
            },
            "Mold Wizard (注塑模具向导)": {
                "type": "Automated Injection Mold Engineering",
                "workflows": ["Product Orientation & Shrinkage", "Parting Lines / Shut-off Surfaces", "Core and Cavity Extraction", "Standard Mold Base (HASCO, DME, LKM, FUTABA)", "Sliders & Angle Pins", "Lifter Mechanisms", "Ejector Pin Layout", "Cooling Channel Circuits", "Runner & Gate System"],
                "api_interfaces": ["NXOpen.MoldWizard", "UF_MOLD"]
            },
            "Progressive Die Wizard (级进模向导)": {
                "type": "Automated Stamping Tool Design",
                "workflows": ["Sheet Metal Blank Unfolding", "Scrap Strip Layout & Pitch Optimization", "Piercing Punch Design", "Bending Insert Forming", "Die Base Assembly"]
            },
            "Mechatronics Concept Designer (MCD)": {
                "type": "Physics-Based Virtual Commissioning",
                "capabilities": ["Rigid Bodies", "Collision Sensors", "Kinematic Joints", "Speed Controllers", "PLC Signal Coupling (OPC UA, SIMIT, PROFINET)"]
            }
        }
    },

    "AutoCAD 2026": {
        "vendor": "Autodesk",
        "api_types": ["AutoLISP / Visual LISP", "ObjectARX C++", "AutoCAD .NET (C# / VB.NET)", "JavaScript API"],
        "core_features": {
            "geometric_drafting": ["LINE", "PLINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE", "RECTANG", "POLYGON", "BOUNDARY", "REGION"],
            "annotation_and_standards": ["DIMLINEAR", "DIMALIGNED", "DIMRADIUS", "DIMDIAMETER", "DIMANGULAR", "TOLERANCE", "LEADER", "QLEADER", "HATCH", "TEXT", "MTEXT"],
            "layers_and_display": ["-LAYER", "COLOR", "LINETYPE", "LWEIGHT", "VIEW", "VPLAYER", "ZOOM", "PAN", "UCS"],
            "blocks_and_attributes": ["BLOCK", "INSERT", "ATTDEF", "BATTMAN", "WBLOCK", "XREF"]
        },
        "plugins_and_addins": {
            "Parametric Constraints (参数化约束引擎)": {
                "type": "2D Geometric and Dimensional Constraint Solver",
                "geometric_constraints": ["GEOMCONSTRAINT: Coincident, Collinear, Concentric, Fix, Parallel, Perpendicular, Horizontal, Vertical, Tangent, Smooth, Symmetric, Equal"],
                "dimensional_constraints": ["DIMCONSTRAINT: Horizontal, Vertical, Aligned, Radial, Diameter, Angular"],
                "equation_solver": ["Parameter Manager", "User Variables (e.g., d1=OuterDia/2, w=d1*sin(30))"]
            },
            "Dynamic Blocks (动态块系统)": {
                "type": "Adaptive Parametric 2D Library",
                "parameters": ["Point", "Linear", "Polar", "XY", "Rotation", "Alignment", "Flip", "Visibility", "Lookup"],
                "actions": ["Move", "Scale", "Stretch", "Polar Stretch", "Rotate", "Flip", "Array", "Lookup Table"]
            },
            "AutoCAD Mechanical Toolset": {
                "type": "Standardized Mechanical Drafting Suite",
                "capabilities": ["Standard Parts (ISO/GB/DIN/JIS Screws, Pins, Shafts)", "Shaft & Bearing Generator", "Spring Calculation", "BOM & Balloons Auto-Tracking", "GD&T Feature Control Frames", "Surface Roughness & Welding Symbols"]
            },
            "Visual LISP ActiveX Bridge": {
                "type": "High-Speed COM Automation Interface",
                "functions": ["vl-load-com", "vlax-ename->vla-object", "vla-AddLightWeightPolyline", "vla-AddDimAligned", "vla-put-Layer", "vla-put-Color"]
            }
        }
    },

    "Vericut 9.6": {
        "vendor": "CGTech",
        "api_types": ["Vericut Project Configuration (.opt / .vcproject)", "Vericut Command Scripts (.cmd)", "C/C++ User API"],
        "core_features": {
            "machine_kinematics_tree": ["Base", "X/Y/Z Linear Axes", "A/B/C Rotary Axes", "Spindle", "Tool Turret", "Chuck/Fixture", "Stock", "Sub-Spindle"],
            "verification_engine": ["Material Removal Simulation", "Solid Voxel Stock Modeling", "Rapid Traverse Collision Detection", "Holder and Spindle Clearance Checking"],
            "collision_and_near_miss": ["Component-to-Component Pairs", "GougeTolerance (default 0.005mm)", "ExcessTolerance", "NearMissDistance", "Stop-On-Error"]
        },
        "plugins_and_addins": {
            "Force Optimization (物理力学切削优化)": {
                "type": "Physics-Based Cutting Mechanics Engine",
                "principles": ["Material Specific Yield Stress", "Chip Thickness Regulation", "Cutting Force Limiting (Fc, Ft, Fr)", "Spindle Power & Torque Thresholds", "Tool Deflection Minimization"],
                "benefits": ["Eliminate Tool Breakage", "Reduce Cycle Time by 15-40%", "Extend Tool Life", "Prevent Chatter/Vibration in Deep Pockets"]
            },
            "OptiPath (体积去除率进给率优化)": {
                "type": "Geometric Feed Rate Regulation",
                "principles": ["Constant Material Removal Rate (MRR)", "Corner Slowdown / Deceleration", "Air-Cut Acceleration", "Adaptive Depth-of-Cut Feed Adjustment"]
            },
            "AUTO-DIFF (自动比对与过切残料分析)": {
                "type": "As-Machined Stock vs. Design CAD Model Comparison",
                "comparison_inputs": ["Design CAD Model (STEP, Parasolid, CATIA, NX)", "Simulated Workpiece Stock"],
                "heatmaps": ["Green: In-Tolerance (+/- tolerance band)", "Blue: Excess Stock (Under-machined)", "Red: Gouge / Undercut (Scrapped part)", "Gray: Out of envelope"]
            },
            "CNC Machine Emulation (数控机床系统虚拟解释器)": {
                "controllers": ["FANUC 0i/30i/31i", "Siemens Sinumerik 840D sl / ONE", "Heidenhain TNC 640", "Mazak SmoothX", "Haas NGC"],
                "advanced_macro_support": ["G68.2 (Tilted Working Plane)", "G43.4 / G43.5 (RTCP / TCPM)", "TRAORI (Siemens 5-Axis)", "CYCLE800 (Siemens Swivel Plane)", "PLANE SPATIAL (Heidenhain)"]
            }
        }
    },

    "CIMCO Edit 2026": {
        "vendor": "CIMCO Integration",
        "api_types": ["FANUC / Siemens / Heidenhain NC Code", "Macro B Scripting", "External DNC Control API"],
        "core_features": {
            "code_editor": ["Syntax Highlighting", "Renumbering Blocks", "G-Code Mirroring & Scaling", "Coordinate Transformation", "Cycle Time Estimator"],
            "backplotter": ["2D Turning Plot", "3D Mill Wireframe Toolpath", "Solid Tool Simulation", "Multi-Axis Swivel Visualization", "Rapid Traverse Inspection"],
            "multi_channel_sync": ["Dual-Turret Synchronization", "Wait Code Matching (M100/M200)", "Sub-Spindle Part Transfer Validation"]
        },
        "plugins_and_addins": {
            "Macro B Parametric Interpreter": {
                "type": "Mathematical CNC Cycle & Family-of-Parts Logic Engine",
                "variables": [
                    "#1-#33: Local variables (arguments in G65 macro call)",
                    "#100-#199: Volatile common variables (reset on power-cycle)",
                    "#500-#999: Non-volatile persistent variables",
                    "#1000-#1035: Interface input signals",
                    "#3000: User alarm generation (e.g., #3000=1 (OVERCUT ERROR))",
                    "#3006: Operator message with programmed stop"
                ],
                "math_functions": ["SQRT[]", "ABS[]", "ROUND[]", "FIX[]", "FUP[]", "BIN[]", "BCD[]", "SIN[]", "COS[]", "TAN[]", "ATAN[][]"],
                "logical_branching": ["IF [...] GOTO n", "WHILE [...] DO m ... END m", "EQ", "NE", "GT", "GE", "LT", "LE"]
            },
            "DNC-Max & NC-Base Integration": {
                "type": "Shop Floor Program Management and Machine Communication",
                "features": ["RS-232 / Ethernet TCP/IP Transmission", "Revision History & Audit Trail", "User Privilege Access Control", "Wireless Barcode Triggering"]
            },
            "Tool Manager & Setup Sheet": {
                "type": "Cutter Assembly & Shop Documentation Engine",
                "features": ["Tool Diameter, Flute Length, Corner Radius, Gauge Length Export", "Automated HTML/PDF Setup Sheet Generation for CNC Operators"]
            }
        }
    },

    "斯沃数控仿真软件 (SSCNC)": {
        "vendor": "Nanjing Swan Software Technology",
        "api_types": ["SSCNC Project Session (.ssc)", "FANUC / SIEMENS / HEIDENHAIN Panel Emulation", "Virtual Hardware Machine Settings"],
        "core_features": {
            "virtual_machines": ["Slant Bed 2-Axis CNC Lathe", "Horizontal Turning Center with Live Tools (C/Y-Axis)", "3-Axis Vertical Machining Center", "5-Axis Trunnion Milling Center"],
            "control_systems": ["FANUC 0i-TF / 0i-TD / 0i-MF", "SIEMENS 828D / 840D", "HEIDENHAIN iTNC 530", "MITSUBISHI M70/M80", "GSK 988T / 980TDb", "HNC 818A"],
            "panel_operations": ["AUTO (Memory)", "EDIT (Program Entry)", "MDI (Manual Data Input)", "JOG (Continuous Jog)", "HANDLE (MPG Handwheel)", "REF (Return Reference Zero)"]
        },
        "plugins_and_addins": {
            "Workpiece & Clamping Setup (工件装夹系统)": {
                "types": ["3-Jaw Hydraulic Chuck", "Collet Chuck", "Pneumatic Machine Vise", "T-Slot Clamping Kit"],
                "parameters": ["Blank Diameter / Length", "Chuck Clamping Depth", "Clamp Force (MPa)", "Soft Jaw Bore Diameter", "Tailstock Center Engagement"]
            },
            "Tool Turret & Library Setup (刀塔刀库装配)": {
                "types": [
                    "OD Rough Turning Tool (T0101, 80 deg diamond)",
                    "OD Finish Turning Tool (35 deg diamond)",
                    "Grooving / Cutoff Tool (Blade width 3.0mm)",
                    "Threading Tool (60 deg triangular insert)",
                    "Internal Boring Bar (Min bore 16mm)",
                    "Center Drill & Twist Drill",
                    "Face Mill & Flat Endmill & Ballnose Endmill"
                ],
                "parameters": [
                    "Tool Station T01~T12",
                    "Tool Nose Radius r_eps (0.2, 0.4, 0.8mm)",
                    "Tool Direction Quadrant (T1~T9: T3=Standard Right-Hand OD, T8=OD Plunge Grooving, T2=Standard ID Boring, T9=Mill Center)"
                ]
            },
            "Touch-Off & WCS Calibration (对刀与工件坐标系校准)": {
                "methods": [
                    "Trial Cut Method (试切对刀法): Turn OD -> Measure Dia D -> Input X[D] -> Measure -> Face End -> Input Z0.0 -> Measure -> Save to G54",
                    "Optical Tool Setter Probe (对刀仪对刀): Jog tool to touch probe sensor X/Z edges -> Automatic offset calculation",
                    "Dial Indicator Alignment (百分表找正): Center alignment of cylindrical parts on 4-jaw chuck or machine vise"
                ],
                "offset_registers": [
                    "G54~G59 Work Coordinate Registers",
                    "Geometry Offset (GEOM) X/Z/R/T",
                    "Wear Offset (WEAR) X/Z for dimension micro-compensation (+/-0.02mm)"
                ]
            }
        }
    }
}
