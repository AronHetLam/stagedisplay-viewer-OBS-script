# stagedisplay-viewer-OBS-script
This script for OBS studio makes you able to get slide text from Propresenter directly to OBS, without having to record the output and key out the background color. It works by setting one or two text sources to the current slides text. 

Only testet on Windows 10 with ProPresenter 6. 

Installation:
1. Make sure you have python 3.6.6 64-bit installed as OBS by default uses 64-bit version, and that you have linked to the Python directory within OBS. (OBS documentation states that only Python 3.6 is supported on Windows)
2. Within Propresenter, Enable Stagedisplay App.
Choose "Preferences" under the "ProPresenter 6" tab, and go to the "Network" tab within Preferences. Tick off "Enable Network" and "Enable Stage Display App". Select a password and a port number, and remember those for later.
3. Add one or two text sources (GDI+) to a scene in OBS, which the script can use to display the slide text from ProPresenter. If you use two sources the script is able to make a fading animation between changing slides - in this case, make sure the layout and tranformation of both sources are the same for best looking results.
4. Add the script to OBS. Choose "Scripts" under the "Tools" tab, and hit the plus sign in the Scripts window, and link to the script. I recommend copying the script to OBS' default directory for scripts to keep it nice and tidy, since OBS will add a "__pycache__" folder whereever the script is.
4. By selecting the Script from the list of script, you should see the script properties (if not, there must have been an error loading or rynning it. Again, make sure you set up Python right). Here you can select the text source(s) you created for the purpose, and put in the information needed to establish the connection to ProPresenter. Put in the IP-address of the host PC/Mac, or "localhost" if you have ProPresenter running on the same PC as OBS. Put in the password and port number that you put in Propresenter, and by default the script will connect within a few seconds.
5. Try to change slides in ProPresenter, and see if the text changes in OBS. There might be slight delays while ProPresenter for windows only sends out the the changes a few times each second. 

Warning: 
-By later on changing the names of used text sources, you will need to reload the script, and select the text sources again. 
