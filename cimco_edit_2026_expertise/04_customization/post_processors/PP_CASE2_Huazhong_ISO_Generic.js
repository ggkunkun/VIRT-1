// Global Variables that defines the layout of the 
// various program blocks
globals = {
	decimalMark: ".",
	linebreak: "\n",
	variableDelimeter: " ",
	tolerance: 0.02,
	showSequenceNumbers: true,
	sequenceNumberStart: 10,
	sequenceNumberIncrement: 5,
	useRadius: false,
	absoluteArcCenter: false,
	xyFirstMove:true,  // Should the first linear move be made XY the Z or Z then XY

	// Use useHelixLinearization to enable or disable the substitution of helix movements
	// if set to true all helix movements will be substituted by line movements with the
	// tolerance of helixLinearizationTolerance
	useHelixLinearization: true,
	helixLinearizationTolerance: 0.02
};


// PostInfo is used to give a description of the post processor.
// All the fields have to be present. The type defines if the post is 
// used for milling or turning
PostInfo = {
	title: "Huazhong HNC ISO Generic (B-03 non-native)",
	summary: "Default Post Processor built for CNC-Calc V.7",
	description: "ISO_G-Code generic adaptation for Huazhong controllers - NOT officially supported by CIMCO (B-03); requires on-machine verification",
	author: "Virtu CNC Support (derived from Cimco A/S)",
	version: "1.0-HNC-ISO",
	type: POST_TYPE_MILL
};


propertyNames = {
	RetractPlane: 1,
	SafeDistance: 1,
	ReferenceHeight: 1,
	Depth: 1,
	PlungeFeedRate: 1,
	RetractFeedRate: 1,
	FirstPeckDepth: 1,
	SubsequentPeckDepth: 1
};


// DrillFields
// This array of structures describes which parameter field should be
// enabled in the parameter dialog for drilling in CNC-Calc
// The name of the operation must be unique because it is used to identify the 
// operation in onDrillHeader, onDrillPoint and onDrillFooter
// isLonghand defines if the drilling routine should be shown as 
// a Cycle or a longhand routine
MillDrillingFields = [
	{
		name: "Drilling G81",
		isLonghand: false,
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
		name: "Spot Drilling G82",
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
		lowerDwell: true,
		pitch: false,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "Standard Peck Drilling G83",
		isLonghand: false,
		plungingFeedrate: true,
		retractFeedrate: false,
		firstDepth: true,
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
		name: "Rapid Peck Drilling G73",
		isLonghand: false,
		plungingFeedrate: true,
		retractFeedrate: false,
		firstDepth: true,
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
		name: "Reaming G89",
		isLonghand: false,
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
		name: "CW Rigid Tapping G84",
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
		lowerDwell: true,
		pitch: true,
		tappingSpeed: false,
		retractSpeed: false
	},
	{
		name: "CCW Rigid Tapping G74",
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
		lowerDwell: true,
		pitch: false,
		tappingSpeed: true,
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

var commentFront = "(";
var commentBack = ")";

var gFormat;
var fFormat;
var fFormatOneDecimal;
var xyzFormat;
var pFormat;

var radiusFormat;

var gOutput;

var feedOutput;
var feedOutputOneDecimal;
var compensationOutput;

var xOutput;
var yOutput;
var zOutput;

var iOutput;
var jOutput;
var kOutput;

var pOutput;
var qOutput;
var rOutput;

var radiusOutput;

var feedRates;
var lastCompensation;

var dwellOutput;

var sequenceNumber;

var calcSafeDistance;
var calcEndDepth;
var drillHeaderCalled = false;
var drillIsFirst;
var drillHeader;

// Used in Longhand Drill Operations
var absoluteSafeDistance;
var incrementalSafeDistance;

var isFirstMove;

// Variables to use for axis Substitution
var useAxisSubstitution = false;
var axisSubstitutionDiameter;
var axisSubstitutionTolerance;
var axisSubstitutionOutput;

// writeBlock
// Is used to format a standard block with the correct 
// block numbering.
// The block numbering is setup in the globals variable at 
// the top of the program
function writeBlock() {
	if (globals.showSequenceNumbers) {
		writeWords2("N" + sequenceNumber, arguments);
		sequenceNumber += globals.sequenceNumberIncrement;
	} else {
		writeWords(arguments);
	}
}

// getFeedrate
// Returns the correct feedrate based on the movement type
function getFeedrate(movement) {
	if (! (movement in feedRates)) {
		return "";
	}
	return feedOutput.format(feedRates[movement]);
}

// getCompensation
// Returns the correct compensation code
function getCompensation() {
	var gCode;
	switch (lastCompensation) {
		case COMPENSATION_LEFT : gCode = 41; break;
		case COMPENSATION_RIGHT: gCode = 42; break;
		case COMPENSATION_OFF  : gCode = 40; break;
	}
	if (lastCompensation != null) {
		return compensationOutput.format(gCode);
	}
	return "";
}

// onInit
// Should be the first function called in the post processor
// Normally all formats and output variables should be defined
// inside the onOnit function
function onInit() {
	// createFormat handles value pairs to control the behaviour of the format
	// Their order is without importance and the value pairs supported and their default values are:
	//	Name			Default value	Description
	// 	prefix..........""..............What should be written in front of the value
	// 	width			0				Indicates the width or the integer part of the value
	// 	zeropad.........false...........Zeropad relates to the integer part of the value and if a width of
	//									4 is set and zeropad is set to true 1 would be written as 0001
	// 	decimals........0...............Indicates the number of decimals the value should be formatted with
	// 	scale			1				This is a scale factor that the value is multiplied by 		
	// 	forceDecimal....false...........Forces the decimal part of the value to always be written wit the number
	//									of decimals indicated in decimals so if decimals is set to 3 and forceDecimals
	//									is set to true 3.0 would be written as 3.000
	// 	forceSign.......false...........Makes it possible to always force a sign. So 4.25 would be written as +4.25

	// Examples:
	// myFormat = createFormat({prefix: "H", decimals: 1, width:3, zeropad: true}) 2.7 becomes H002,7
	// myFormat = createFormat({decimals: 3, forceDecimals: true, forceSign: true}) 4.5 becomes +4.500

	gFormat = createFormat({prefix: "G", decimals: 0, width: 2, forceDelim:false});
	fFormat = createFormat({decimals: 0, prefix: "F", forceDelim: false });
	fFormatOneDecimal = createFormat({prefix: "F", decimals: 1, forceDecimal: true});
	xyzFormat = createFormat({decimals: 3, forceDecimal: true});
	pFormat = createFormat({decimals: 0, forceDecimal: true})
	intFormat = createFormat({decimals: 0});
	mFormat = createFormat({decimals: 0, width: 2});

	gOutput = createVariable({}, gFormat);

	radiusFormat = createFormat({decimals: 3, forceDecimal: true});

	feedOutput = createVariable({}, fFormat);
	feedOutputOneDecimal = createVariable({}, fFormatOneDecimal);

	compensationOutput = createVariable({}, gFormat);

	xOutput = createVariable({prefix: "X"}, xyzFormat);
	yOutput = createVariable({prefix: "Y"}, xyzFormat);
	zOutput = createVariable({prefix: "Z"}, xyzFormat);

	iOutput = createVariable({prefix: "I", force: true}, xyzFormat);
	jOutput = createVariable({prefix: "J", force: true}, xyzFormat);
	kOutput = createVariable({prefix: "K", force: true}, xyzFormat);

	pOutput = createVariable({prefix: "P", force: true}, intFormat);
	sOutput = createVariable({prefix: "S", force: true}, intFormat);
	tOutput = createVariable({prefix: "T", force: true}, mFormat);
	mOutput = createVariable({prefix: "M", force: true}, mFormat);
	qOutput = createVariable({prefix: "Q", force: true}, xyzFormat);
	rOutput = createVariable({prefix: "R", force: true}, xyzFormat);

	radiusOutput = createVariable({prefix: "R", force: true},radiusFormat);

	feedRates = {};
	lastCompensation = null;
	
	dwellOutput = createVariable({prefix: "X", force: true}, xyzFormat);
	
	sequenceNumber = globals.sequenceNumberStart;

	drillIsFirst = false;
	drillHeader = null;

	isFirstMove = true;
}

function onOpen(isClipboard){
	exportToClipboard = isClipboard;

	if (exportToClipboard) 
	{
		onComment("Exporting to Clipboard");
	}
	else
	{
		onComment("Exporting to Editor");
	}
}

function onClose(){
	if (!exportToClipboard) {
		writeBlock("M30");
	}
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

function onSpindleRotation(rotation)
{

}

function onToolChange(toolData)
{
	var m = mOutput.format(6);
	var t = tOutput.format(toolData.toolNumber);
	var s = sOutput.format(toolData.spindleSpeed);
	var f = feedOutput.format(toolData.feedrate);
	writeBlock(t, m, s, f);
}

function onComment(text){
	var comment = commentFront + text + commentBack;

	writeBlock(comment); 
}

function onLinear(vx_, vy_, vz_, movement) 
{
	if (useAxisSubstitution)
	{
		var g
		var x;
		var y;
		var z;
		var f;
		var c;
		// Split the first move in a XY and a Z move
		if(isFirstMove)
		{
			isFirstMove = false;
			
			if (movement == MOVE_RAPID) 
			{
				g = gOutput.format(0);
			} else 
			{
				g = gOutput.format(1);
			}

			f = getFeedrate(movement);
			c = getCompensation();

			if (globals.xyFirstMove) 
			{
				x = xOutput.format(vx_);
				
				y = yOutput.format(0.0);
				writeBlock(g,y,f); // Just a dummy move to Y0.00 to satisfy backplot!!
			
				if (movement == MOVE_RAPID) 
				{
					g = gOutput.format(0);
				} else 
				{
					g = gOutput.format(1);
				}
				
				// calculate the axis angle
				var axisAngle = 360.0 * (vy_ / (Math.PI * axisSubstitutionDiameter));
				var b = axisSubstitutionOutput.format(axisAngle);
				writeBlock(c, g, x, b, f);
			}
			else
			{
				var zVal = vz_ + axisSubstitutionDiameter / 2.0;
				z = zOutput.format(zVal);
				writeBlock(c, g, z, f);
			}
		}

		if (movement == MOVE_RAPID) {
			g = gOutput.format(0);
		} else 
		{
			g = gOutput.format(1);
		}
		
		x = xOutput.format(vx_);
		// calculate the axis angle
		var axisAngle = 360.0 * (vy_ / (Math.PI * axisSubstitutionDiameter));
		var b = axisSubstitutionOutput.format(axisAngle);
		var zVal = vz_ + axisSubstitutionDiameter / 2.0;
		z = zOutput.format(zVal);
		var setLastY = yOutput.format(vy_);
		f = getFeedrate(movement);
		c = getCompensation();
		writeBlock(c, g, x, b, z, f);
	}
	else
	{
		var g
		var x;
		var y;
		var z;
		var f;
		var c;
		
		// Split the first move in a XY and a Z move
		if(isFirstMove)
		{
			isFirstMove = false;

			if (movement == MOVE_RAPID) 
			{
				g = gOutput.format(0);
			} else 
			{
				g = gOutput.format(1);
			}

			f = getFeedrate(movement);
			c = getCompensation();

			if (globals.xyFirstMove) 
			{
				x = xOutput.format(vx_);
				y = yOutput.format(vy_);
				writeBlock(c, g, x, y, f);
			}
			else
			{
				z = zOutput.format(vz_);
				writeBlock(c, g, z, f);
			}
		}

		if (movement == MOVE_RAPID) {
			g = gOutput.format(0);
		} else 
		{
			g = gOutput.format(1);
		}
		
		x = xOutput.format(vx_);
		y = yOutput.format(vy_);
		z = zOutput.format(vz_);
		f = getFeedrate(movement);
		c = getCompensation();
		writeBlock(c, g, x, y, z, f);
	}
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
	
	// make i, j, k relative
	var i = cx - lastX;
	var j = cy - lastY;
	var k = cz - lastZ;

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
		if (globals.absoluteArcCenter) 
		{
			i = cx;
			j = cy;
			k = cz;
		}
		
		
		// center of circle
		i = iOutput.format(i);
		j = jOutput.format(j);
		k = kOutput.format(k);
		
		// final position
		var x = xOutput.format(ex);
		var y = yOutput.format(ey);
		var z = zOutput.format(ez);

		if (x || y || z) 
		{
			// g code and compensation
			gOutput.reset();
			var g = gOutput.format(isCW ? 2 : 3);
			var c = getCompensation();
			// feed rate
			var f = getFeedrate(movement);

			if (globals.useRadius) 
			{
				var radius = Math.sqrt(((cx - ex) * (cx - ex)) + 
									   ((cy - ey) * (cy - ey)));

				var r = radiusOutput.format(radius);

				writeBlock(c, g, x, y, z, r, f);
			}
			else
			{
				writeBlock(c, g, x, y, z, i, j, k, f);
			}
		}
	}
}

function onCompensation(comp) {
	lastCompensation = comp;
}

function onDwell(seconds) {
	writeBlock(gOutput.format(4), dwellOutput.format(seconds));
}

function onDrillingHeader(obj) {
	// indicate that the drill header was called 
	drillHeaderCalled = true;
	
	// Indicate that the next hole (onDrillPoint) is the first hole after the header
	drillIsFirst = true;
	drillHeader = obj;
	onComment(drillHeader.name)
	
	// Calculate the safe distance
	if (drillHeader.safeDistanceIsAbsolute)
	{
		calcSafeDistance = drillHeader.safeDistance;
	}
	else
	{
		calcSafeDistance = drillHeader.referencePlane + drillHeader.safeDistance;
	}

	if (drillHeader.endDepthIsAbsolute) 
	{
		calcEndDepth = drillHeader.endDepth;
	}
	else
	{
		calcEndDepth = drillHeader.referencePlane + drillHeader.endDepth
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

		// Used to indicate that the drill should return to Initial Level between holes
		var g98 = gOutput.format(98);

		if (drillIsFirst) 
		{
			if (drillHeader.name != "Export Holes")
			{
				// Move to the X,Y position and then move down to the Initial level
				var gRapidMove = gOutput.format(0);
				writeBlock(gRapidMove,x,y);
				writeBlock(gRapidMove,z);
			}

			drillIsFirst = false;
	// 		xOutput.reset();
	// 		yOutput.reset();
	// 		zOutput.reset();

			if (drillHeader.name == "Drilling G81") 
			{
				// G98 G81 X Y Z R F
				// G98 Return to initial height after the hole is drilled
				// G81 Drilling Cycle
				// X Coordinate of the hole
				// Y Coordinate of the hole
				// Z Distance from the safe plane to the bottom of the hole
				// R The distance from the initial level to the safe plane
				// F Feedrate for the drilling operation

				// G81 Drilling Cycle
				var g81 = gOutput.format(81);

				// Z Distance from the safe plane to the bottom of the hole
				z = zOutput.format(calcEndDepth);

				// R The distance from the initial level to the safe plane
				var r = rOutput.format(calcSafeDistance);

				// F Feedrate for the drilling operation
				var f = feedOutput.format(drillHeader.plungingFeedrate);

				writeBlock(g98,g81, x, y, z, r, f);

			}else if (drillHeader.name == "Spot Drilling G82")
			{
				// G98 G82 X Y Z R P F
				// G98 Return to initial height after the hole is drilled
				// G82 Spot drilling cycle with dwell at the bottom
				// X Coordinate of the hole
				// Y Coordinate of the hole
				// Z Distance from the safe plane to the bottom of the hole
				// R The distance from the initial level to the safe plane
				// P The dwell time at the bottom of the hole in mili seconds
				// F Feedrate for the drilling operation

				// G82 Spot drilling cycle with dwell at the bottom
				var g82 = gOutput.format(82);

				// Z Distance from the safe plane to the bottom of the hole
				z = zOutput.format(calcEndDepth);

				// R The distance from the initial level to the safe plane
				var r = rOutput.format(calcSafeDistance);

				// P The dwell time at the bottom of the hole in miliseconds 
				var p = "";

				if (drillHeader.useBottomDwelling) 
				{
					p = pOutput.format(drillHeader.bottomDwelling * 1000);
				}
				
				// F Feedrate for the drilling operation
				var f = feedOutput.format(drillHeader.plungingFeedrate);

				writeBlock(g98,g82, x, y, z, r, p, f);
			}else if (drillHeader.name == "Standard Peck Drilling G83")
			{
				// G98 G83 X Y Z P R F
				// G98 Return to initial height after the hole is drilled
				// G83 Standard peck drilling cycle
				// X Coordinate of the hole
				// Y Coordinate of the hole
				// Z Distance from the safe plane to the bottom of the hole
				// R The distance from the initial level to the safe plane
				// Q is the pecking depth for each peck
				// F Feedrate for the drilling operation

				// G83 Standard peck drilling cycle
				var g83 = gOutput.format(83);
				
				// Z Distance from the safe plane to the bottom of the hole
				z = zOutput.format(calcEndDepth);

				// R is the distance from the initial height to safe distance
				var r = rOutput.format(calcSafeDistance);

				// Q is the pecking depth for each peck
				var q = qOutput.format(drillHeader.firstDepth);
				
				// F Feedrate for the drilling operation
				var f = feedOutput.format(drillHeader.plungingFeedrate);

				writeBlock(g98,g83, x, y, z, r, q, f);
			}else if (drillHeader.name == "Rapid Peck Drilling G73")
			{
				// G98 G73 X Y Z P R F
				// G98 Return to initial height after the hole is drilled
				// G73 Rapid peck drilling cycle
				// X Coordinate of the hole
				// Y Coordinate of the hole
				// Z Distance from the safe plane to the bottom of the hole
				// R The distance from the initial level to the safe plane
				// Q is the pecking depth for each peck
				// F Feedrate for the drilling operation

				// G83 Standard peck drilling cycle
				var g73 = gOutput.format(73);
				
				// Z Distance from the safe plane to the bottom of the hole
				z = zOutput.format(calcEndDepth);

				// R is the distance from the initial height to safe distance
				var r = rOutput.format(calcSafeDistance);

				// P is the pecking depth for each peck
				var q = qOutput.format(drillHeader.firstDepth);
				
				// F Feedrate for the drilling operation
				var f = feedOutput.format(drillHeader.plungingFeedrate);

				writeBlock(g98,g73, x, y, z, r, q, f);
			}else if (drillHeader.name == "Reaming G89")
			{
				// G98 G89 X Y Z R P F
				// G98 Return to initial height after the hole is drilled
				// G89 Boring cycle that dwells at buttom and retracts with feed 
				// X Coordinate of the hole
				// Y Coordinate of the hole
				// Z Distance from the safe plane to the bottom of the hole
				// R The distance from the initial level to the safe plane
				// P is the dwell time at the bottom of the hole in mili seconds
				// F Feedrate for the drilling operation

				// G89 Boring cycle that dwells at buttom and retracts with feed 
				var g89 = gOutput.format(89);
				
				// Z Distance from the safe plane to the bottom of the hole
				z = zOutput.format(calcEndDepth);

				// R is the distance from the initial height to safe distance
				var r = rOutput.format(calcSafeDistance);

				// P is the bottom dwell time in mili seconds
				var p = "";

				if (drillHeader.useBottomDwelling) 
				{
					p = pOutput.format(drillHeader.bottomDwelling * 1000);
				}
				
				// F Feedrate for the drilling operation
				var f = feedOutput.format(drillHeader.plungingFeedrate);

				writeBlock(g98,g89, x, y, z, r, p, f);
			}else if (drillHeader.name == "Export Holes")
			{
	// 			x = xOutput.format(x);
	// 			y = yOutput.format(y);
				writeBlock(x, y);
			}else if (drillHeader.name == "CW Rigid Tapping G84")
			{			
				// G98 G95 G84 X Y Z R P F
				// G98 Return to initial height after the hole is drilled
				// G95 Indicates the the feed is given as pitch in mm/revolution
				// G84 CW Rigid tapping cycle
				// X Coordinate of the hole
				// Y Coordinate of the hole
				// Z Distance from the safe plane to the bottom of the hole
				// R The distance from the initial level to the safe plane
				// P The dwell time at the bottom of the hole in mili seconds
				// F Pitch for the drilling operation in mm/rev because of the G95

				// G84 CW Rigid tapping cycle
				var g84 = gOutput.format(84);

				// G95 Indicates the the feed is given as 0.01mm/revolution
				var g95 = gOutput.format(95);

				// Z Distance from the safe plane (R) to the bottom of the hole
				z = zOutput.format(calcEndDepth);

				// R is the distance from the initial height to safe distance
				var r = rOutput.format(calcSafeDistance);

				// P is the bottom dwell time in miliseconds
				var p = "";

				if (drillHeader.useBottomDwelling) 
				{
					p = pOutput.format(drillHeader.bottomDwelling * 1000);
				}
				
				var f = feedOutputOneDecimal.format(drillHeader.pitch);

				writeBlock(g98,g84, x, y, z, r, p, f);
			}else if (drillHeader.name == "CCW Rigid Tapping G74")
			{
				// G98 G95 G74 X Y Z R P F
				// G98 Return to initial height after the hole is drilled
				// G95 Indicates the the feed is given as pitch in mm/revolution
				// G74 CCW Rigid tapping cycle
				// X Coordinate of the hole
				// Y Coordinate of the hole
				// Z Distance from the safe plane to the bottom of the hole
				// R The distance from the initial level to the safe plane
				// P The dwell time at the bottom of the hole in mili seconds
				// F Pitch for the drilling operation in mm/rev because of the G95

				// G74 CW Rigid tapping cycle
				var g74 = gOutput.format(74);
				
				// G95 Indicates the the feed is given as 0.01mm/revolution
				var g95 = gOutput.format(95);

				// Z Distance from the safe plane (R) to the bottom of the hole
				z = zOutput.format(calcEndDepth);

				// R is the distance from the initial height to safe distance
				var r = rOutput.format(calcSafeDistance);

				// P is the bottom dwell time in mili seconds
				var p = "";

				if (drillHeader.useBottomDwelling) 
				{
					p = pOutput.format(drillHeader.bottomDwelling * 1000);
				}
				
				var f = feedOutputOneDecimal.format(drillHeader.pitch);

				writeBlock(g98,g95,g74, x, y, z, r, p, f);
			}
		} else //drillFirst
		{
			writeBlock(x, y);
		}
	} 
	else // (!drillHeader.isLonghand) 
	{
		var z;
		var x = xOutput.format(xCoord);
		var y = yOutput.format(yCoord);
		var g = gOutput.format(0); 
	
		writeBlock(g,x,y); // Make the X Y Entry Move
	
		if (drillIsFirst)
		{
			drillIsFirst = false;
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(drillHeader.retractPlane);
			g = gOutput.format(0); 
		
			writeBlock(g,x,y,z); // Make the Entry Move to Retract Height
		}
		
		x = xOutput.format(xCoord);
		y = yOutput.format(yCoord);
		z = zOutput.format(absoluteSafeDistance);
		g = gOutput.format(0); 
		
		writeBlock(g,x,y,z); // Make the Entry Move to Safe Height
		
		// Now we are ready to make the drilling from safe Distance
		
		if (drillHeader.name == "Drilling")
		{

			// Drill down with feed
			g = gOutput.format(1);
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(absoluteEndDepth);
			
			if(drillHeader.usePlungingFeedrate)
			{
				var f = feedOutput.format(drillHeader.plungingFeedrate);
				writeBlock(g, x, y, z, f);
			}
			else
			{
				writeBlock(g, x, y, z);
			}
		}
		else if(drillHeader.name == "Spot Drilling")
		{
			// Drill down with feed
			g = gOutput.format(1);
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(absoluteEndDepth);
			
			if(drillHeader.usePlungingFeedrate)
			{
				var f = feedOutput.format(drillHeader.plungingFeedrate);
				writeBlock(g, x, y, z, f);
			}
			else
			{
				writeBlock(g, x, y, z);
			}
			
			// Dwell at bottom if used
			if(drillHeader.useBottomDwelling)
			{
				g = gOutput.format(4);
				var dwell = dwellOutput.format(drillHeader.bottomDwelling);
				writeBlock(g,dwell);
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
				g = gOutput.format(1);
				x = xOutput.format(xCoord);
				y = yOutput.format(yCoord);
				z = zOutput.format(absoluteEndDepth + restDepth);
				
				if(drillHeader.usePlungingFeedrate)
				{
					var f = feedOutput.format(drillHeader.plungingFeedrate);
					writeBlock(g, x, y, z, f);
				}
				else
				{
					writeBlock(g, x, y, z);
				}
				
				// Dwell at bottom if used
				if(drillHeader.useBottomDwelling)
				{
					g = gOutput.format(4);
					var dwell = dwellOutput.format(drillHeader.bottomDwelling);
					writeBlock(g,dwell);
				}
				
				// Retract to safe distance
				x = xOutput.format(xCoord);
				y = yOutput.format(yCoord);
				z = zOutput.format(drillHeader.referencePlane + incrementalSafeDistance);
				
				if(drillHeader.usePlungingFeedrate && drillHeader.useRetractFeedrate)
				{
					g = gOutput.format(1);
					var f = feedOutput.format(drillHeader.retractFeedrate);
					writeBlock(g, x, y, z, f);
				}
				else
				{
					g = gOutput.format(0);
					writeBlock(g, x, y, z);
				}
				
				// Dwell at top if used
				if(drillHeader.useTopDwelling)
				{
					g = gOutput.format(4);
					var dwell = dwellOutput.format(drillHeader.topDwelling);
					writeBlock(g,dwell);
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
			    g = gOutput.format(1);
				x = xOutput.format(xCoord);
				y = yOutput.format(yCoord);
				z = zOutput.format(absoluteEndDepth + restDepth);
				
				if(drillHeader.usePlungingFeedrate)
				{
					var f = feedOutput.format(drillHeader.plungingFeedrate);
					writeBlock(g, x, y, z, f);
				}
				else
				{
					writeBlock(g, x, y, z);
				}
				
				// Dwell at bottom if used
				if(drillHeader.useBottomDwelling)
				{
					g = gOutput.format(4);
					var dwell = dwellOutput.format(drillHeader.bottomDwelling);
					writeBlock(g,dwell);
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
						g = gOutput.format(1);
						var f = feedOutput.format(drillHeader.retractFeedrate);
						writeBlock(g, x, y, z, f);
					}
					else
					{
						g = gOutput.format(0);
						writeBlock(g, x, y, z);
					}

					// Dwell at top if used
					if(drillHeader.useTopDwelling)
					{
						g = gOutput.format(4);
						var dwell = dwellOutput.format(drillHeader.topDwelling);
						writeBlock(g,dwell);
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
				g = gOutput.format(1);
				var f = feedOutput.format(drillHeader.retractFeedrate);
				writeBlock(g, x, y, z, f);
			}
			else
			{
				g = gOutput.format(0);
				writeBlock(g, x, y, z);
			}

			// Dwell at top if used
			if(drillHeader.useTopDwelling)
			{
				g = gOutput.format(4);
				var dwell = dwellOutput.format(drillHeader.topDwelling);
				writeBlock(g,dwell);
			}
		}
		else if(drillHeader.name == "Reaming")
		{
			// Drill down with feed
			g = gOutput.format(1);
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(absoluteEndDepth);
			
			if(drillHeader.usePlungingFeedrate)
			{
				var f = feedOutput.format(drillHeader.plungingFeedrate);
				writeBlock(g, x, y, z, f);
			}
			else
			{
				writeBlock(g, x, y, z);
			}
			
			// Dwell at bottom if used
			if(drillHeader.useBottomDwelling)
			{
				g = gOutput.format(4);
				var dwell = dwellOutput.format(drillHeader.bottomDwelling);
				writeBlock(g,dwell);
			}

			// always move here
			x = xOutput.format(xCoord);
			y = yOutput.format(yCoord);
			z = zOutput.format(absoluteSafeDistance);
			// Retract with retract feed rate or rapid
			if(drillHeader.usePlungingFeedrate && drillHeader.useRetractFeedrate)
			{
				g = gOutput.format(1);
				var f = feedOutput.format(drillHeader.retractFeedrate);
				writeBlock(g, x, y, z, f);
			}
			else
			{
				g = gOutput.format(0);
				writeBlock(g,x,y,z);
			}
			
			// Dwell at top if used
			if(drillHeader.useTopDwelling)
			{
				g = gOutput.format(4);
				var dwell = dwellOutput.format(drillHeader.topDwelling);
				writeBlock(g,dwell);
			}
		}
		
		// Make the final retract to the reference height
		g = gOutput.format(0);
		x = xOutput.format(xCoord);
		y = yOutput.format(yCoord);
		z = zOutput.format(drillHeader.retractPlane);
		writeBlock(g,x,y,z);
	}
}

function onDrillingFooter() 
{
	// indicate that we have no valid drill header 
	drillHeaderCalled = false;
	
	if (!drillHeader.isLonghand) 
	{
		if (drillHeader.name != "Export Holes")
		{
			writeBlock(gOutput.format(80));
		}
	}
	else // (!drillHeader.isLonghand) 
	{
	}
}

function setFeedrate(movement, feedRate) {
	feedRates[movement] = feedRate;
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

