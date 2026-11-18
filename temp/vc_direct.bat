@echo off
setlocal
set CGTECH_INSTALL=E:\
set CGTECH_PRODUCTS=E:\windows64
set LSHOST=localhost
set CGTECH_CLASSES=E:\classes
set CGTECH_LIBDIR=E:\library\
set CGTECH_LIBRARY=E:\library\;E:\samples\TLS;E:\samples\Support_files
set CGTECH_LICENSE=E:\windows64\license
set CGTECH_LOCALE=chinese_simplified
set CGTECH_LANGUAGE=E:\classes\lang\chinese_simplified
set CGTECH_SAMPLES=E:\samples\
set CGTECH_DEFAULT_UNITS=MILLIMETER
set CGTECH_RGB_TXT=E:\windows64\vericut\rgbhues.txt
set CGTECH_VTPD_FILE=E:\windows64\resources\VTPD.db
set CGTECH_SURFACE_TEXTURES_DIR=E:\library\surface_textures
set CGTECH_IGNORE_LAST=TRUE
set PATH=E:\windows64\vericut;%PATH%
cd /d %~dp1
E:\windows64\jre\bin\java.exe -Djogamp.gluegen.UseTempJarCache=false -Dsun.java2d.noddraw=true -XX:+UseG1GC -XX:+UseStringDeduplication -XX:ReservedCodeCacheSize=128m -Xms512m -Xmx1536m -Xss2m --module-path=E:\windows64\javafx\lib --add-modules=javafx.swing,javafx.web --add-exports=java.base/java.lang=ALL-UNNAMED --add-exports=java.desktop/sun.awt=ALL-UNNAMED --add-exports=java.desktop/sun.java2d=ALL-UNNAMED --add-exports=javafx.graphics/com.sun.glass.ui=ALL-UNNAMED -classpath "E:\classes;E:\classes\CGTech.jar" com.cgtech.Vericut BATCH batchp ip=%~1 > stdout.txt 2> stderr.txt
echo EXIT=%ERRORLEVEL%
