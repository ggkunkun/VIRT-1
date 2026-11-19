globals = {
	decimalMark: ".",
	linebreak: "\n",
	variableDelimeter: " ",
	tolerance: 0.02,
	showSequenceNumbers: true,
	sequenceNumberStart: 10,
	sequenceNumberIncrement: 5,
	xyFirstMove:true,  // Should the first linear move be made XY the Z or Z then XY
	
	// Use useHelixLinearization to enable or disable the substitution of helix movements
	// if set to true all helix movements will be substituted by line movements with the
	// tolerance of helixLinearizationTolerance
	useHelixLinearization: false,
	helixLinearizationTolerance: 0.01
};

PostInfo = {
	title: "Heidenhain",
	summary: "Default Post Processor built for CNC-Calc V.7",
	description: "This is a Post Processor built for the Heidenhain controllers used on a mill",
	author: "Cimco A/S",
	version: "1.0",
	type: POST_TYPE_MILL
};

propertyNames = {
	RetractPlane: 1,
	SafeDistance: 1,
	ReferenceHeight: 1,
	Depth: 1,
	PlungeFeedrate: 1,
	RetractFeedrate: 1,
	FirstPeckDepth: 1,
	SubsequentPeckDepth: 1
};

MillDrillingFields = [
	{
		name: "Cycle 200 Drilling",
		isLonghand: false,
		plungingFeedrate: true,
		retractFeedrate: false,
		firstDepth: true,
		degressionType: false,
		degression: false,
		peckingRetract: false,
		minimumDepth: false,
		firstFeedrateFactor: false,
		upperDwell: true,
		lowerDwell: true,
		pitch: false,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Cycle 201 Reaming",
		isLonghand: false,
		plungingFeedrate: true,
		retractFeedrate: true,
		firstDepth: false,
		degressionType: false,
		degression: false,
		peckingRetract: false,
		minimumDepth: false,
		firstFeedrateFactor: false,
		upperDwell: false,
		lowerDwell: true,
		pitch: false,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Cycle 203 Universal Drilling",
		isLonghand: false,
		plungingFeedrate: true,
		retractFeedrate: true,
		firstDepth: true,
		degressionType: false,
		degression: true,
		peckingRetract: true,
		minimumDepth: true,
		firstFeedrateFactor: false,
		upperDwell: true,
		lowerDwell: true,
		pitch: false,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Cycle 207 CW Rigid Tapping",
		isLonghand: false,
		plungingFeedrate: false,
		retractFeedrate: false,
		firstDepth: false,
		degressionType: false,
		degression: false,
		peckingRetract: false,
		minimumDepth: false,
		firstFeedrateFactor: false,
		upperDwell: false,
		lowerDwell: false,
		pitch: true,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Cycle 207 CCW Rigid Tapping",
		isLonghand: false,
		plungingFeedrate: false,
		retractFeedrate: false,
		firstDepth: false,
		degressionType: false,
		degression: false,
		peckingRetract: false,
		minimumDepth: false,
		firstFeedrateFactor: false,
		upperDwell: false,
		lowerDwell: false,
		pitch: true,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Export Holes",
		isLonghand: false,
		plungingFeedrate: false,
		retractFeedrate: false,
		firstDepth: false,
		degressionType: false,
		degression: false,
		peckingRetract: false,
		minimumDepth: false,
		firstFeedrateFactor: false,
		upperDwell: false,
		lowerDwell: false,
		pitch: false,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Drilling",
		isLonghand: true,
		plungingFeedrate: true,
		retractFeedrate: false,
		firstDepth: false,
		degressionType: false,
		degression: false,
		peckingRetract: false,
		minimumDepth: false,
		firstFeedrateFactor: false,
		upperDwell: false,
		lowerDwell: false,
		pitch: false,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Spot Drilling",
		isLonghand: true,
		plungingFeedrate: true,
		retractFeedrate: false,
		firstDepth: false,
		degressionType: false,
		degression: false,
		peckingRetract: false,
		minimumDepth: false,
		firstFeedrateFactor: false,
		upperDwell: false,
		lowerDwell: true,
		pitch: false,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Standard Peck Drilling",
		isLonghand: true,
		plungingFeedrate: true,
		retractFeedrate: true,
		firstDepth: true,
		degressionType: true,
		degression: true,
		peckingRetract: false,
		minimumDepth: true,
		firstFeedrateFactor: false,
		upperDwell: true,
		lowerDwell: true,
		pitch: false,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Rapid Peck Drilling",
		isLonghand: true,
		plungingFeedrate: true,
		retractFeedrate: true,
		firstDepth: true,
		degressionType: true,
		degression: true,
		peckingRetract: true,
		minimumDepth: true,
		firstFeedrateFactor: false,
		upperDwell: true,
		lowerDwell: true,
		pitch: false,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Reaming",
		isLonghand: true,
		plungingFeedrate: true,
		retractFeedrate: true,
		firstDepth: false,
		degressionType: false,
		degression: false,
		peckingRetract: false,
		minimumDepth: false,
		firstFeedrateFactor: false,
		upperDwell: true,
		lowerDwell: true,
		pitch: false,
		tappingSpeed: false,
		retractSpeed: false
	}
];

var commentFront = ";";
var commentBack = "";

var gFormat;
var fFormat;
var xyzFormat;

var gOutput;

var paramFormat;
var paramOutput;

var defaultDoubleFormat;
var defaultDoubleOutput;

var feedOutput;
var compensationOutput;

var xOutput;
var yOutput;
var zOutput;

var iOutput;
var jOutput;
var kOutput;

var feedrates;

var sweepOutput;

var lastCompensation;
var compensationTmp;

var dwellOutput;

var sequenceNumber;

// Used to handle drill cycles
var drillHeaderCalled = false;
var drillIsFirst;
var drillHeader;

var isFirstMove;

// Variables to handle drilling parameters
var retractDistance; // Used as Second Safety Clearance
var safeDistance;  // Used as Safety Clearance
var referenceHeight; // Used as Surface Coordinate 
var depth;

// Used in Longhand Drill Operations
var absoluteSafeDistance;
var incrementalSafeDistance;

// Variables to use for axis Substitution
var useAxisSubstitution = false;
var axisSubstitutionDiameter;
var axisSubstitutionTolerance;
var axisSubstitutionOutput;

function writeBlock() {
	if (globals.showSequenceNumbers) {
		writeWords2(sequenceNumber, arguments);
		sequenceNumber += globals.sequenceNumberIncrement;
	} else {
		writeWords(arguments);
	}
}

function getFeedrate(movement) {
	if (movement == MOVE_RAPID) {
		return "FMAX";
	}
	if (! (movement in feedrates)) {
		return "F";
	}
	return feedOutput.format(feedrates[movement]) || "F";
}

function getCompensation() {
	if (lastCompensation == compensationTmp) {
		return "R";
	}
	compensationTmp = lastCompensation;
	switch (lastCompensation) {
		case COMPENSATION_LEFT : return "RL"; break;
		case COMPENSATION_RIGHT: return "RR"; break;
		case COMPENSATION_OFF  : return "R0"; break;
	}
}

function reset() {
	xOutput.reset();
	yOutput.reset();
	zOutput.reset();
}

function onInit() {
	gFormat = createFormat({prefix: "G", decimals: 0, width: 2, forceDelim:false});
	fFormat = createFormat({decimals: 0, prefix: "F", forceDelim: false});
	xyzFormat = createFormat({decimals: 3, forceDecimal: true});
	intFormat = createFormat({decimals: 0});
	paramFormat = createFormat({prefix:"Q", decimals: 0, forceDelim:false});
	paramOutput = createVariable({force: true},paramFormat);


	defaultDoubleFormat = createFormat({decimals: 3});
	defaultDoubleOutput = createVariable({force: true},defaultDoubleFormat);

	gOutput = createVariable({}, gFormat);

	feedOutput = createVariable({}, fFormat);
	compensationOutput = createVariable({}, gFormat);



	xOutput = createVariable({prefix: "X"}, xyzFormat);
	yOutput = createVariable({prefix: "Y"}, xyzFormat);
	zOutput = createVariable({prefix: "Z"}, xyzFormat);

	iOutput = createVariable({prefix: "I", force: true}, xyzFormat);
	jOutput = createVariable({prefix: "J", force: true}, xyzFormat);
	kOutput = createVariable({prefix: "K", force: true}, xyzFormat);
	
	sweepOutput = createVariable({prefix: "IPA", force: true}, xyzFormat);

	sOutput = createVariable({prefix: "S", force: true}, intFormat);
	tOutput = createVariable({prefix: "TOOL CALL ", force: true}, intFormat);
	
	feedrates = {};

	lastCompensation = null;
	compensationTmp = null;
	
	dwellOutput = createVariable({force: true}, xyzFormat);
	
	sequenceNumber = globals.sequenceNumberStart;

	isFirstMove = true;
}

function onComment(text){
	var comment = commentFront + text + commentBack;

	writeBlock(comment); 
}

function onAxisSubstitutionStart(axisName, diameter, axisTolerance)
{
	useAxisSubstitution = true;
	axisSubstitutionTolerance = axisTolerance;
	axisSubstitutionDiameter = diameter;
	axisSubstitutionOutput = createVariable({prefix: axisName}, xyzFormat);
}

function onAxisSubstitutionEnd()
{
	useAxisSubstitution = false;
}

function onSpindleRotation(rotation){

}

function onToolChange(toolData)
{
	var t = tOutput.format(toolData.toolNumber);
	var s = sOutput.format(toolData.spindleSpeed);
	var f = feedOutput.format(toolData.feedrate);
	writeBlock(t, s, f);
}

function onLinear(vx_, vy_, vz_, movement) 
{
	if (useAxisSubstitution)
	{
		var x;
		var y;
		var z;
		var f;
		var r;
		var m = "M";
		
		// Split the first move in a XY and a Z move
		if(isFirstMove)
		{
			isFirstMove = false;
			
			f = getFeedrate(movement);
			r = getCompensation();

			if (globals.xyFirstMove) 
			{
				x = xOutput.format(vx_);
				
				y = yOutput.format(0.0);
				writeBlock("L",y,r ,f, m); // Just a dummy move to Y0.00 to satisfy backplot!!
			
				// calculate the axis angle
				var axisAngle = 360.0 * (vy_ / (Math.PI * axisSubstitutionDiameter));
				var b = axisSubstitutionOutput.format(axisAngle);
				writeBlock("L", x, b, r, f, m);
			}
			else
			{
				var zVal = vz_ + axisSubstitutionDiameter / 2.0;
				z = zOutput.format(zVal);
				writeBlock("L", z, r, f,m);
			}
		}

		x = xOutput.format(vx_);
		// calculate the axis angle
		var axisAngle = 360.0 * (vy_ / (Math.PI * axisSubstitutionDiameter));
		var b = axisSubstitutionOutput.format(axisAngle);
		var zVal = vz_ + axisSubstitutionDiameter / 2.0;
		z = zOutput.format(zVal);
		var setLastY = yOutput.format(vy_);
		f = getFeedrate(movement);
		r = getCompensation();
		writeBlock("L", x, b, z, r, f, m);
	}
	else
	{
		var x;
		var y;
		var z;
		var r;
		var f;
		var m = "M";
		
		
		// Split the first move in a XY and a Z move
		if(isFirstMove)
		{
			isFirstMove = false;

			f = getFeedrate(movement);
			r = getCompensation();

			if (globals.xyFirstMove) 
			{
				x = xOutput.format(vx_);
				y = yOutput.format(vy_);
				writeBlock("L", x, y, r, f, m);
			}
			else
			{
				z = zOutput.format(vz_);
				writeBlock("L", z, r, f, m);
			}
		}

		x = xOutput.format(vx_);
		y = yOutput.format(vy_);
		z = zOutput.format(vz_);
		r = getCompensation();
		f = getFeedrate(movement);
		writeBlock("L", x, y, z, r, f, m);
	}
}

function onLinearXY(x,y,movement) {
	var r = getCompensation();
	var f = getFeedrate(movement);
	var m = "M";
	writeBlock("L", x, y, r, f, m);
}

function onLinearZ(z,movement) {
	var r = getCompensation();
	var f = getFeedrate(movement);
	var m = "M";
	writeBlock("L", z, r, f, m);
}

function onCircular(cx, cy, cz, ex, ey, ez, isCW, movement) 
{
	var tolerance = globals.helixLinearizationTolerance;
	
	if (useAxisSubstitution)
	{
		tolerance = axisSubstitutionTolerance;
	}
	
	// current position
	var lastX = xOutput.getLast();
	var lastY = yOutput.getLast();
	var lastZ = zOutput.getLast();
	
	if (useAxisSubstitution)
	{
		lastZ = lastZ - axisSubstitutionDiameter / 2.0;
	}
	
	if(useAxisSubstitution || (globals.useHelixLinearization && ez != lastZ))
	{
		var startVector = new Vector2(lastX, lastY);
		var centerVector = new Vector2(cx, cy);
		var endVector = new Vector2(ex, ey);
		
		var r1Vector = vectorUnit2(vectorSubtract2(startVector, centerVector));
		var r2Vector = vectorUnit2(vectorSubtract2(endVector, centerVector));
		
		var yVector = new Vector2( -1 * r1Vector.y, r1Vector.x);
		if (isCW) {
			yVector = new Vector2(-1 * yVector.x, -1 * yVector.y);
		}
		var sweep = Math.atan2( vectorDot2(r2Vector, yVector), vectorDot2(r2Vector, r1Vector) );
		
		if (sweep < 0) {
			sweep = sweep + 2 * Math.PI;
		}
		
		if (! isCW) {
			sweep = Math.abs(sweep);
		} else {
			sweep = -1 * Math.abs(sweep);
		}
		
		var startAngle = (Math.atan2(lastY - cy,lastX - cx) + 2 * Math.PI) % (2 * Math.PI);
		startAngle = startAngle%(2 * Math.PI);
		var endAngle = (Math.atan2(ey - cy,ex - cx) + 2 * Math.PI) % (2 * Math.PI);
		endAngle = endAngle % (2 * Math.PI);
  
		var radius = Math.sqrt(((cx - ex) * (cx - ex)) + ((cy - ey) * (cy - ey)));
		var m=Math.round(sweep * Math.sqrt(radius/tolerance/8)+1);
		var deltaZ = (ez-lastZ)/Math.abs(m);

		var sign = 1;
		
		if (m < 0)
		{
			//sign = -1.0;
			m = Math.abs(m);
		}
		
		if ( m > 0 )
		{
			for (var n = 1;n <= m;n++)
			{
				var calcSweep = n * (sweep / m) + startAngle;
				
				var xCoordinate = cx + radius * Math.cos(calcSweep);
				var yCoordinate = cy + radius * Math.sin(calcSweep);

				var zCoordinate = lastZ + deltaZ * n;

				onLinear(xCoordinate,yCoordinate,zCoordinate,movement);
			}
		}
		else
		{
			onLinear(ex,ey,ez,movement);
		}
	}
	else
	{
		xOutput.reset();
		yOutput.reset();
		zOutput.reset();


		var cxf = xOutput.format(cx);
		var cyf = yOutput.format(cy);
		var czf = zOutput.format(cz);
		
		reset();
		
		// final position
		var exf = xOutput.format(ex);
		var eyf = yOutput.format(ey);
		var ezf = zOutput.format(ez);
		
		// feed rate, direction, m
		var f = getFeedrate(movement);
		var dr = isCW ? "DR-" : "DR+";
		var r = getCompensation();
		var m = "M";
		
		// IPA
		if (Math.abs(lastZ - ez) > globals.tolerance) {
			function vectorString(v) { return "x: " + v.x + ", y: " + v.y;}
			var startVector = new Vector2(lastX, lastY);
			var centerVector = new Vector2(cx, cy);
			var endVector = new Vector2(ex, ey);
			
			var r1Vector = vectorUnit2(vectorSubtract2(startVector, centerVector));
			var r2Vector = vectorUnit2(vectorSubtract2(endVector, centerVector));
			
			var yVector = new Vector2( -1 * r1Vector.y, r1Vector.x);
			if (isCW) {
				yVector = new Vector2(-1 * yVector.x, -1 * yVector.y);
			}
			var sweep = Math.atan2( vectorDot2(r2Vector, yVector), vectorDot2(r2Vector, r1Vector) );
			
			if (sweep < 0) {
				sweep = sweep + 2 * Math.PI;
			}
			
			if (! isCW) {
				sweep = Math.abs(sweep);
			} else {
				sweep = -1 * Math.abs(sweep);
			}
			sweep = 180.0 * (sweep / Math.PI);
			
			var sweepf = sweepOutput.format(sweep);
			writeBlock("CC", cxf, cyf);
			writeBlock("CP", sweepf, ezf, dr);
		} else {

			var moveDistance = Math.sqrt((lastX - ex)*(lastX - ex)+(lastY - ey)*(lastY - ey)); // We never have full circles here

			if (moveDistance > globals.tolerance ) 
			{
			writeBlock("CC", cxf, cyf);
			writeBlock("C", exf, eyf, dr, r, f, m);
			}
		}
	}
}

function onCompensation(compensation) {
	lastCompensation = compensation;
}

function onDwell(seconds) {
	writeBlock("CYCL DEF 9.0 DWELL TIME");
	writeBlock("CYCL DEF 9.1 DWELL", '"' + dwellOutput.format(seconds) + '"');
	writeBlock("CYCL CALL");
}

function onDrillingHeader(obj) {
	// indicate that the drill header was called 
	drillHeaderCalled = true;
	
	// Indicate that the next hole (onDrillingPoint) is the first hole after the header
	drillIsFirst = true;
	drillHeader = obj;
	onComment(drillHeader.name);
	
	
	// Calculate the various parameters
	retractDistance = drillHeader.retractPlane - drillHeader.referencePlane; // Used as Second Safety Clearance
	
	if (drillHeader.safeDistanceIsAbsolute) 
	{
		safeDistance = drillHeader.safeDistance;
	}
	else
	{
		safeDistance = drillHeader.safeDistance + drillHeader.referencePlane;
	}

	referenceHeight = drillHeader.referencePlane;

	if (drillHeader.endDepthIsAbsolute) 
	{
		depth = drillHeader.endDepth;
	}
	else
	{
		depth = drillHeader.referencePlane + drillHeader.endDepth;
	}
	
	// Calculate the safe distance
	// Used in Longhand operations
	if (drillHeader.safeDistanceIsAbsolute)
	{
		absoluteSafeDistance = drillHeader.safeDistance;
		incrementalSafeDistance = drillHeader.safeDistance - drillHeader.referencePlane;
	}
	else
	{
		absoluteSafeDistance = drillHeader.referencePlane + drillHeader.safeDistance;
		incrementalSafeDistance = drillHeader.safeDistance;
	}

	if (drillHeader.endDepthIsAbsolute) 
	{
		absoluteEndDepth = drillHeader.endDepth;
	}
	else
	{
		absoluteEndDepth = drillHeader.referencePlane + drillHeader.endDepth;
	}
}

function onDrillingPoint(xCoord, yCoord) 
{
	if (!drillHeader.isLonghand) 
	{
		var x = xOutput.format(xCoord);
		var y = yOutput.format(yCoord);
		var z = zOutput.format(drillHeader.retractPlane);
	
		var endTilde = " ~ ";
		
		if (drillIsFirst) 
		{
			drillIsFirst = false;
	
			if (drillHeader.name != "Export Holes")
			{
				var r = getCompensation();
				var f = getFeedrate(MOVE_RAPID);
				var m = "M";
				writeBlock("L", x, y, r, f, m);

				var r = getCompensation();
				var f = getFeedrate(MOVE_RAPID);
				var m = "M";
				writeBlock("L", z, r, f, m);

			}

			if (drillHeader.name == "Cycle 200 Drilling") 
			{
				writeBlock("CYCL DEF 200 DRILLING");
				var paramLines = {};
				var lineCount = 0;
				paramLines[lineCount++] = "    " + paramOutput.format(200) + "=" + 
										  defaultDoubleOutput.format(safeDistance) +
										  "  " + commentFront + "SAFETY CLEARANCE" + endTilde + commentBack; 

				paramLines[lineCount++] = "    " + paramOutput.format(201) + "=" + 
										  defaultDoubleOutput.format(depth) +
										  "  " + commentFront + "DEPTH" + endTilde + commentBack; 


				// Parameter 206 Plunging Feedrate
				// If usePlunging feed rate is not selected then it will use the feed rate for plunging
				// and if that is not set the it will use the feedrate for cutting
				paramLines[lineCount] = "    " + paramOutput.format(206) + "=";
				if (drillHeader.usePlungingFeedrate) 
				{
					 paramLines[lineCount] += defaultDoubleOutput.format(drillHeader.plungingFeedrate);						  
				}
				else
				{
					// if no feedrate is given use the plunge or cutting feedrate
					var plungingFeedrate = feedrates[MOVE_CUTTING];

					if (MOVE_PLUNGE in feedrates) 
					{
						plungingFeedrate = feedrates[MOVE_PLUNGE];
					}

					paramLines[lineCount] += defaultDoubleOutput.format(plungingFeedrate);
				}
				
				paramLines[lineCount++] += "  " + commentFront + "FEED RATE FOR PLUNGING" + endTilde + commentBack; 


				// Parameter 202 Infeed Depth (pecking depth)
				if (drillHeader.useBottomDwelling) 
				{
					paramLines[lineCount++] = "    " + paramOutput.format(202) + "=" + 
											  defaultDoubleOutput.format(drillHeader.firstDepth) +
											  "  " + commentFront + "INFEED DEPTH" + endTilde + commentBack; 
				}
				
				// Parameter 210 Dwell Time at Top
				if (drillHeader.useBottomDwelling) 
				{
					paramLines[lineCount++] = "    " + paramOutput.format(210) + "=" + 
											  defaultDoubleOutput.format(drillHeader.bottomDwelling) +
											  "  " + commentFront + "DWELL TIME AT TOP" + endTilde + commentBack; 
				}
				else
				{
					paramLines[lineCount++] = "    " + paramOutput.format(210) + "=" + 
											  defaultDoubleOutput.format(0.0) +
											  "  " + commentFront + "DWELL TIME AT TOP" + endTilde + commentBack; 
				}


				// Parameter 203 Surface Coordinate (Reference Plane)
				paramLines[lineCount++] = "    " + paramOutput.format(203) + "=" + 
										  defaultDoubleOutput.format(drillHeader.referencePlane) +
										  "  " + commentFront + "SURFACE COORDINATE" + endTilde + commentBack; 

				// Parameter 204 Safety Clearance (Retract Plane)
				paramLines[lineCount++] = "    " + paramOutput.format(204) + "=" + 
										  defaultDoubleOutput.format(retractDistance) +
										  "  " + commentFront + "2ND SAFETY CLEARANCE" + endTilde + commentBack; 

				// Parameter 211 Bottom Dwelling
				if (drillHeader.useBottomDwelling) 
				{
					paramLines[lineCount++] = "    " + paramOutput.format(211) + "=" + 
											  defaultDoubleOutput.format(drillHeader.bottomDwelling) +
											  "  " + commentFront + "DWELL TIME AT DEPTH" + endTilde + commentBack; 
				}
				else
				{
					paramLines[lineCount++] = "    " + paramOutput.format(211) + "=" + 
											  defaultDoubleOutput.format(0.0) +
											  "  " + commentFront + "DWELL TIME AT DEPTH" + endTilde + commentBack; 
				}
				

				for (var lineCounter = 0;lineCounter < lineCount;lineCounter++) 
				{
					writeln(paramLines[lineCounter]);
				}
				writeBlock("CYCL CALL");
			}else if (drillHeader.name == "Cycle 203 Universal Drilling")
			{
				writeBlock("CYCL DEF 203 UNIVERSAL DRILLING");
				var paramLines = {};
				var lineCount = 0;
				paramLines[lineCount++] = "    " + paramOutput.format(200) + "=" + 
										  defaultDoubleOutput.format(safeDistance) +
										  "  " + commentFront + "SAFETY CLEARANCE" + endTilde + commentBack; 

				paramLines[lineCount++] = "    " + paramOutput.format(201) + "=" + 
										  defaultDoubleOutput.format(depth) +
										  "  " + commentFront + "DEPTH" + endTilde + commentBack; 

				// Parameter 206 Plunging Feedrate
				// If usePlunging feed rate is not selected then it will use the feed rate for plunging
				// and if that is not set the it will use the feedrate for cutting
				paramLines[lineCount] = "    " + paramOutput.format(206) + "=";
				if (drillHeader.usePlungingFeedrate) 
				{
					 paramLines[lineCount] += defaultDoubleOutput.format(drillHeader.plungingFeedrate);						  
				}
				else
				{
					// if no feedrate is given use the plunge or cutting feedrate
					var plungingFeedrate = feedrates[MOVE_CUTTING];

					if (MOVE_PLUNGE in feedrates) 
					{
						plungingFeedrate = feedrates[MOVE_PLUNGE];
					}

					paramLines[lineCount] += defaultDoubleOutput.format(plungingFeedrate);
				}
				
				paramLines[lineCount++] += "  " + commentFront + "FEED RATE FOR PLUNGING" + endTilde + commentBack; 


				// Parameter 202 Infeed Depth (pecking depth)
				if (drillHeader.useBottomDwelling) 
				{
					paramLines[lineCount++] = "    " + paramOutput.format(202) + "=" + 
											  defaultDoubleOutput.format(drillHeader.firstDepth) +
											  "  " + commentFront + "INFEED DEPTH" + endTilde + commentBack; 
				}
				
				// Parameter 210 Dwell Time at Top
				if (drillHeader.useBottomDwelling) 
				{
					paramLines[lineCount++] = "    " + paramOutput.format(210) + "=" + 
											  defaultDoubleOutput.format(drillHeader.bottomDwelling) +
											  "  " + commentFront + "DWELL TIME AT TOP" + endTilde + commentBack; 
				}
				else
				{
					paramLines[lineCount++] = "    " + paramOutput.format(210) + "=" + 
											  defaultDoubleOutput.format(0.0) +
											  "  " + commentFront + "DWELL TIME AT TOP" + endTilde + commentBack; 
				}


				// Parameter 203 Surface Coordinate (Reference Plane)
				paramLines[lineCount++] = "    " + paramOutput.format(203) + "=" + 
										  defaultDoubleOutput.format(drillHeader.referencePlane) +
										  "  " + commentFront + "SURFACE COORDINATE" + endTilde + commentBack; 

				// Parameter 204 Safety Clearance (Retract Plane)
				paramLines[lineCount++] = "    " + paramOutput.format(204) + "=" + 
										  defaultDoubleOutput.format(retractDistance) +
										  "  " + commentFront + "2ND SAFETY CLEARANCE" + endTilde + commentBack; 

				// Parameter 212 Decrement (degrssion)
				paramLines[lineCount++] = "    " + paramOutput.format(212) + "=" + 
										  defaultDoubleOutput.format(drillHeader.degression) +
										  "  " + commentFront + "DECREMENT" + endTilde + commentBack; 


				// Parameter 213 Breaks (Number of pecks between full retract)
				paramLines[lineCount++] = "    " + paramOutput.format(213) + "=" + 
										  defaultDoubleOutput.format(1) +
										  "  " + commentFront + "BREAKS" + endTilde + commentBack; 

				// Parameter 205 Min. Infeed Depth
				paramLines[lineCount++] = "    " + paramOutput.format(205) + "=" + 
										  defaultDoubleOutput.format(drillHeader.minimumDepth) +
										  "  " + commentFront + "MIN. INFEED DEPTH" + endTilde + commentBack; 

				// Parameter 211 Bottom Dwelling
				if (drillHeader.useBottomDwelling) 
				{
					paramLines[lineCount++] = "    " + paramOutput.format(211) + "=" + 
											  defaultDoubleOutput.format(drillHeader.bottomDwelling) +
											  "  " + commentFront + "DWELL TIME AT DEPTH" + endTilde + commentBack; 
				}
				else
				{
					paramLines[lineCount++] = "    " + paramOutput.format(211) + "=" + 
											  defaultDoubleOutput.format(0.0) +
											  "  " + commentFront + "DWELL TIME AT DEPTH" + endTilde + commentBack; 
				}
				
				// Parameter 208 Retract Feedrate
				// If usePlunging feed rate is not selected then it will use the feed rate for plunging
				// and if that is not set the it will use the feedrate for cutting
				paramLines[lineCount] = "    " + paramOutput.format(208) + "=";
				if (drillHeader.useRetractFeedrate) 
				{
					 paramLines[lineCount] += defaultDoubleOutput.format(drillHeader.retractFeedrate);						  
				}
				else
				{
					// if no feedrate is given use the plunge or cutting feedrate
					var plungingFeedrate = feedrates[MOVE_CUTTING];

					if (MOVE_PLUNGE in feedrates) 
					{
						plungingFeedrate = feedrates[MOVE_PLUNGE];
					}

					paramLines[lineCount] += defaultDoubleOutput.format(plungingFeedrate);
				}
				paramLines[lineCount++] += "  " + commentFront + "RETRACTION FEED RATE" + endTilde + commentBack; 

				// Parameter 256 Dist. for chip breaking (pecking retract)
				paramLines[lineCount++] = "    " + paramOutput.format(256) + "=" + 
										  defaultDoubleOutput.format(drillHeader.peckingRetract) +
										  "  " + commentFront + "DIST. FOR CHIP BREAKING" + endTilde + commentBack; 

				for (var lineCounter = 0;lineCounter < lineCount;lineCounter++) 
				{
					writeln(paramLines[lineCounter]);
				}

				writeBlock("CYCL CALL");

			}else if (drillHeader.name == "Cycle 201 Reaming")
			{
				writeBlock("CYCL DEF 201 REIBEN");
				var paramLines = {};
				var lineCount = 0;
				paramLines[lineCount++] = "    " + paramOutput.format(200) + "=" + 
										  defaultDoubleOutput.format(safeDistance) +
										  "  " + commentFront + "SAFETY CLEARANCE" + endTilde + commentBack; 

				paramLines[lineCount++] = "    " + paramOutput.format(201) + "=" + 
										  defaultDoubleOutput.format(depth) +
										  "  " + commentFront + "DEPTH" + endTilde + commentBack; 


				// Parameter 206 Plunging Feedrate
				// If usePlunging feed rate is not selected then it will use the feed rate for plunging
				// and if that is not set the it will use the feedrate for cutting
				paramLines[lineCount] = "    " + paramOutput.format(206) + "=";
				if (drillHeader.usePlungingFeedrate) 
				{
					 paramLines[lineCount] += defaultDoubleOutput.format(drillHeader.plungingFeedrate);						  
				}
				else
				{
					// if no feedrate is given use the plunge or cutting feedrate
					var plungingFeedrate = feedrates[MOVE_CUTTING];

					if (MOVE_PLUNGE in feedrates) 
					{
						plungingFeedrate = feedrates[MOVE_PLUNGE];
					}

					paramLines[lineCount] += defaultDoubleOutput.format(plungingFeedrate);
				}
				
				paramLines[lineCount++] += "  " + commentFront + "FEED RATE FOR PLUNGING" + endTilde + commentBack; 


				// Parameter 211 Bottom Dwelling
				if (drillHeader.useBottomDwelling) 
				{
					paramLines[lineCount++] = "    " + paramOutput.format(211) + "=" + 
											  defaultDoubleOutput.format(drillHeader.bottomDwelling) +
											  "  " + commentFront + "DWELL TIME AT DEPTH" + endTilde + commentBack; 
				}
				else
				{
					paramLines[lineCount++] = "    " + paramOutput.format(211) + "=" + 
											  defaultDoubleOutput.format(0.0) +
											  "  " + commentFront + "DWELL TIME AT DEPTH" + endTilde + commentBack; 
				}

				// Parameter 208 Retract Feedrate
				// If usePlunging feed rate is not selected then it will use the feed rate for plunging
				// and if that is not set the it will use the feedrate for cutting
				paramLines[lineCount] = "    " + paramOutput.format(208) + "=";
				if (drillHeader.useRetractFeedrate) 
				{
					 paramLines[lineCount] += defaultDoubleOutput.format(drillHeader.retractFeedrate);						  
				}
				else
				{
					// if no feedrate is given use the plunge or cutting feedrate
					var plungingFeedrate = feedrates[MOVE_CUTTING];

					if (MOVE_PLUNGE in feedrates) 
					{
						plungingFeedrate = feedrates[MOVE_PLUNGE];
					}

					paramLines[lineCount] += defaultDoubleOutput.format(plungingFeedrate);
				}
				
				paramLines[lineCount++] += "  " + commentFront + "RETRACTION FEED RATE" + endTilde + commentBack; 

				// Parameter 203 Surface Coordinate (Reference Plane)
				paramLines[lineCount++] = "    " + paramOutput.format(203) + "=" + 
										  defaultDoubleOutput.format(drillHeader.referencePlane) +
										  "  " + commentFront + "SURFACE COORDINATE" + endTilde + commentBack; 

				// Parameter 204 Safety Clearance (Retract Plane)
				paramLines[lineCount++] = "    " + paramOutput.format(204) + "=" + 
										  defaultDoubleOutput.format(retractDistance) +
										  "  " + commentFront + "2ND SAFETY CLEARANCE" + endTilde + commentBack; 

				for (var lineCounter = 0;lineCounter < lineCount;lineCounter++) 
				{
					writeln(paramLines[lineCounter]);
				}

				writeBlock("CYCL CALL");

			}else if (drillHeader.name == "Cycle 207 CW Rigid Tapping")
			{	
				writeBlock("CYCL DEF 207 RIGID TAPPING NEW");
				var paramLines = {};
				var lineCount = 0;
				paramLines[lineCount++] = "    " + paramOutput.format(200) + "=" + 
										  defaultDoubleOutput.format(safeDistance) +
										  "  " + commentFront + "SAFETY CLEARANCE" + endTilde + commentBack; 

				paramLines[lineCount++] = "    " + paramOutput.format(201) + "=" + 
										  defaultDoubleOutput.format(depth) +
										  "  " + commentFront + "DEPTH" + endTilde + commentBack; 

				paramLines[lineCount++] = "    " + paramOutput.format(239) + "=" + 
										  defaultDoubleOutput.format(drillHeader.pitch) +
										  "  " + commentFront + "THREAD PITCH" + endTilde + commentBack; 

				// Parameter 203 Surface Coordinate (Reference Plane)
				paramLines[lineCount++] = "    " + paramOutput.format(203) + "=" + 
										  defaultDoubleOutput.format(drillHeader.referencePlane) +
										  "  " + commentFront + "SURFACE COORDINATE" + endTilde + commentBack; 

				// Parameter 204 Safety Clearance (Retract Plane)
				paramLines[lineCount++] = "    " + paramOutput.format(204) + "=" + 
										  defaultDoubleOutput.format(retractDistance) +
										  "  " + commentFront + "2ND SAFETY CLEARANCE" + endTilde + commentBack; 

				for (var lineCounter = 0;lineCounter < lineCount;lineCounter++) 
				{
					writeln(paramLines[lineCounter]);
				}

				writeBlock("CYCL CALL");

			}else if (drillHeader.name =="Cycle 207 CCW Rigid Tapping")
			{
				writeBlock("CYCL DEF 207 RIGID TAPPING NEW");
				var paramLines = {};
				var lineCount = 0;
				paramLines[lineCount++] = "    " + paramOutput.format(200) + "=" + 
										  defaultDoubleOutput.format(safeDistance) +
										  "  " + commentFront + "SAFETY CLEARANCE" + endTilde + commentBack; 

				paramLines[lineCount++] = "    " + paramOutput.format(201) + "=" + 
										  defaultDoubleOutput.format(depth) +
										  "  " + commentFront + "DEPTH" + endTilde + commentBack; 

				paramLines[lineCount++] = "    " + paramOutput.format(239) + "=" + 
										  defaultDoubleOutput.format(-drillHeader.pitch) +
										  "  " + commentFront + "THREAD PITCH" + endTilde + commentBack; 

				// Parameter 203 Surface Coordinate (Reference Plane)
				paramLines[lineCount++] = "    " + paramOutput.format(203) + "=" + 
										  defaultDoubleOutput.format(drillHeader.referencePlane) +
										  "  " + commentFront + "SURFACE COORDINATE" + endTilde + commentBack; 

				// Parameter 204 Safety Clearance (Retract Plane)
				paramLines[lineCount++] = "    " + paramOutput.format(204) + "=" + 
										  defaultDoubleOutput.format(retractDistance) +
										  "  " + commentFront + "2ND SAFETY CLEARANCE" + endTilde + commentBack; 

				for (var lineCounter = 0;lineCounter < lineCount;lineCounter++) 
				{
					writeln(paramLines[lineCounter]);
				}

				writeBlock("CYCL CALL");

			}else if (drillHeader.name == "Export Holes")
			{
				var f = getFeedrate(MOVE_RAPID);
				var m = "M99";
				writeBlock("L", x, y,f, m);
			}
		}else // drillFirst
		{
			if (drillHeader.name != "Drilling") {
				var f = getFeedrate(MOVE_RAPID);
				var m = "M99";
				writeBlock("L", x, y,f, m);
			}
		}
	} 
	else // (!drillHeader.isLonghand) 
	{
		var z;
		var x = xOutput.format(xCoord);
		var y = yOutput.format(yCoord);
	

		writeBlock("L",x,y,"R FMAX M"); // Make the X Y Entry Move
	
		if (drillIsFirst)
		{
			drillIsFirst = false;
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(drillHeader.retractPlane);
		
			writeBlock("L",x,y,z,"R FMAX M"); // Make the Entry Move to Retract Height
		}
		
		x = xOutput.format(xCoord);
		y = yOutput.format(yCoord);
		z = zOutput.format(absoluteSafeDistance);
		
		writeBlock("L",x,y,z,"R FMAX M"); // Make the Entry Move to Safe Height
		
		// Now we are ready to make the drilling from safe Distance
		
		if (drillHeader.name == "Drilling")
		{

			// Drill down with feed
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(absoluteEndDepth);
			
			if(drillHeader.usePlungingFeedrate)
			{
				var f = feedOutput.format(drillHeader.plungingFeedrate);
				
				if (f == "")
				{
					f = "F";
				}
				
				writeBlock("L", x, y, z, "R",f,"M");
			}
			else
			{
				writeBlock("L", x, y, z,"R F M");
			}
		}
		else if(drillHeader.name == "Spot Drilling")
		{
			// Drill down with feed
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(absoluteEndDepth);
			
			if(drillHeader.usePlungingFeedrate)
			{
				var f = feedOutput.format(drillHeader.plungingFeedrate);
				
				if (f == "")
				{
					f = "F";
				}
				
				writeBlock("L", x, y, z, "R",f,"M");
			}
			else
			{
				writeBlock("L", x, y, z,"R F M");
			}
			
			// Dwell at bottom if used
			if(drillHeader.useBottomDwelling)
			{
				onDwell(drillHeader.bottomDwelling);
			}			
		} 
		else if(drillHeader.name == "Standard Peck Drilling")
		{
			// Calculate Cycle
			var isFirstPeck = true;
			var restDepth = drillHeader.referencePlane - absoluteEndDepth;
			var currentPeckDepth = drillHeader.firstDepth;
			var safeDepth = drillHeader.referencePlane + incrementalSafeDistance;

			while (restDepth > 0.0)
			{		
			    restDepth = (restDepth - currentPeckDepth > 0 ? restDepth - currentPeckDepth : 0.0);

			    // make the next peck
			    // Drill down to current depth
				x = xOutput.format(xCoord);
				y = yOutput.format(yCoord);
				z = zOutput.format(absoluteEndDepth + restDepth);
				
				if(drillHeader.usePlungingFeedrate)
				{
					var f = feedOutput.format(drillHeader.plungingFeedrate);
					
					if (f == "")
					{
						f = "F";
					}
				
					writeBlock("L", x, y, z, "R", f, "M");
				}
				else
				{
					writeBlock("L", x, y, z, "R F M");
				}
				
				// Dwell at bottom if used
				if(drillHeader.useBottomDwelling)
				{
					onDwell(drillHeader.bottomDwelling);
				}
				
				// Retract to safe distance
				x = xOutput.format(xCoord);
				y = yOutput.format(yCoord);
				z = zOutput.format(drillHeader.referencePlane + incrementalSafeDistance);
				
				if(drillHeader.usePlungingFeedrate && drillHeader.useRetractFeedrate)
				{
					var f = feedOutput.format(drillHeader.retractFeedrate);
					
					if (f == "")
					{
						f = "F";
					}
				
					writeBlock("L", x, y, z, "R", f, "M");
				}
				else
				{
					writeBlock("L", x, y, z, "R FMAX M");
				}
				
				// Dwell at top if used
				if(drillHeader.useTopDwelling)
				{
					onDwell(drillHeader.topDwelling);
				}
				
				// Calculate the next peck depth fro degression type and degression

				if (drillHeader.degressionType != 0)
				{
					if (drillHeader.degressionType == 1) // Degression type value
					{					
						currentPeckDepth = currentPeckDepth - drillHeader.degression;
					}
					else 
					{
						currentPeckDepth = currentPeckDepth * drillHeader.degression;
					}
					
					if (currentPeckDepth < drillHeader.minimumDepth)
					{
						currentPeckDepth = drillHeader.minimumDepth;
					}
				}

				isFirstPeck = false;
			}
		}
		else if(drillHeader.name == "Rapid Peck Drilling")
		{
			// Calculate Cycle
			var isFirstPeck = true;
			var restDepth = drillHeader.referencePlane - absoluteEndDepth;
			var currentPeckDepth = drillHeader.firstDepth;
			
			while (restDepth > 0.0)
			{
			    restDepth = (restDepth - currentPeckDepth > 0 ? restDepth - currentPeckDepth : 0.0);

			    // make the next peck
			    x = xOutput.format(xCoord);
				y = yOutput.format(yCoord);
				z = zOutput.format(absoluteEndDepth + restDepth);
				
				if(drillHeader.usePlungingFeedrate)
				{
					var f = feedOutput.format(drillHeader.plungingFeedrate);
					
					if (f == "")
					{
						f = "F";
					}
					
					writeBlock("L", x, y, z, "R", f, "M");
				}
				else
				{
					writeBlock("L", x, y, z, "R F M");
				}
				
				// Dwell at bottom if used
				if(drillHeader.useBottomDwelling)
				{
					onDwell(drillHeader.bottomDwelling);
				}
				
				// Retract to safe distance over the current depth
				
				// Make retract movement with dwell
				if (restDepth != 0.0)
				{
					x = xOutput.format(xCoord);
					y = yOutput.format(yCoord);
					z = zOutput.format(absoluteEndDepth + restDepth + drillHeader.peckingRetract);
					
					if(drillHeader.usePlungingFeedrate && drillHeader.useRetractFeedrate)
					{
						var f = feedOutput.format(drillHeader.retractFeedrate);
						
						if (f == "")
						{
							f = "F";
						}
						
						writeBlock("L", x, y, z, "R", f, "M");
					}
					else
					{
						g = gOutput.format(0);
						writeBlock("L", x, y, z, "R F M");
					}

					// Dwell at top if used
					if(drillHeader.useTopDwelling)
					{
						onDwell(drillHeader.topDwelling);
					}
				}
					
				if (drillHeader.degressionType != 0)
				{
					if (drillHeader.degressionType == 1) // Degression type value
					{
						currentPeckDepth = currentPeckDepth - drillHeader.degression;
					}
					else 
					{
						currentPeckDepth = currentPeckDepth * drillHeader.degression;
					}
					
					if (currentPeckDepth < drillHeader.minimumDepth)
					{
						currentPeckDepth = drillHeader.minimumDepth;
					}
				}

				isFirstPeck = false;
			}
			
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(absoluteSafeDistance);
			
			if(drillHeader.usePlungingFeedrate && drillHeader.useRetractFeedrate)
			{
				var f = feedOutput.format(drillHeader.retractFeedrate);
				
				if (f == "")
				{
					f = "F";
				}
				
				writeBlock("L", x, y, z, "R", f, "M");
			}
			else
			{
				writeBlock("L", x, y, z, "R FMAX M");
			}

			// Dwell at top if used
			if(drillHeader.useTopDwelling)
			{
				onDwell(drillHeader.topDwelling);
			}
		}
		else if(drillHeader.name == "Reaming")
		{
			// Drill down with feed
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(absoluteEndDepth);
			
			if(drillHeader.usePlungingFeedrate)
			{
				var f = feedOutput.format(drillHeader.plungingFeedrate);
				
				if (f == "")
				{
					f = "F";
				}
				
				writeBlock("L", x, y, z, "R", f, "M");
			}
			else
			{
				writeBlock("L", x, y, z, "R F M");
			}
			
			// Dwell at bottom if used
			if(drillHeader.useBottomDwelling)
			{
				onDwell(drillHeader.bottomDwelling);
			}

			// always move here
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(absoluteSafeDistance);
			// Retract with retract feed rate or rapid
			if(drillHeader.usePlungingFeedrate && drillHeader.useRetractFeedrate)
			{
				var f = feedOutput.format(drillHeader.retractFeedrate);
				
				if (f == "")
				{
					f = "F";
				}
				
				writeBlock("L", x, y, z, "R", f, "M");
			}
			else
			{
				writeBlock("L",x,y,z, "R FMAX M");
			}
			
			// Dwell at top if used
			if(drillHeader.useTopDwelling)
			{
				onDwell(drillHeader.topDwelling);
			}
		}
		
		// Make the final retract to the reference height
		x = xOutput.format(xCoord);
		y = yOutput.format(yCoord);
		z = zOutput.format(drillHeader.retractPlane);
		writeBlock("L",x,y,z,"R FMAX M");
	}
}

function onDrillingFooter() 
{
	// Do absolutely nothing
}

function getParameter(name) {
	if (! (name in propertyNames)) {
		throw new Error(name + " not a known property");
	}
	if (! (name in globals)) {
		throw new Error(name + " not yet set");
	}
	return globals[name];
}

function setParameter(name, value) {
	if (! (name in propertyNames)) {
		throw new Error(name + " not a known property");
	}
	globals[name] = value;
}

function setFeedrate(movement, feedrate) {
	feedrates[movement] = feedrate;
}
