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
set GALLIUM_DRIVER=llvmpipe
set LIBGL_ALWAYS_SOFTWARE=1
set MESA_GL_VERSION_OVERRIDE=4.6
set MESA_GLSL_VERSION_OVERRIDE=460
set MESA_SHADER_CACHE_DISABLE=true
set PATH=E:\windows64\jre\bin;E:\windows64\vericut;%PATH%
cd /d %~dp1
E:\windows64\jre\bin\java.exe -Djava.library.path="E:\windows64\jre\bin;E:\windows64\vericut" -Djogamp.gluegen.UseTempJarCache=false -Dsun.java2d.noddraw=true -Dsun.java2d.opengl=False -Dsun.java2d.d3d=False -XX:+UseG1GC -XX:+UseStringDeduplication -XX:ReservedCodeCacheSize=256m -Xms1024m -Xmx4096m -Xss2m --module-path=E:\windows64\javafx\lib --add-modules=javafx.swing,javafx.web --add-exports=java.base/java.lang=ALL-UNNAMED --add-exports=java.desktop/sun.awt=ALL-UNNAMED --add-exports=java.desktop/sun.java2d=ALL-UNNAMED --add-exports=javafx.graphics/com.sun.glass.ui=ALL-UNNAMED -classpath "E:\classes;E:\classes\CGTech.jar" com.cgtech.Vericut "vcp=%~1" > gui_stdout.txt 2> gui_stderr.txt
echo EXIT=%ERRORLEVEL%
