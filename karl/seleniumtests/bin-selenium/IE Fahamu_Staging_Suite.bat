' runs test1.html against IE
'saves results as results_ie_Karlhost01_Fahamu_Suite.html

echo " runs test1.html against IE"
echo "saves results as results_ie_Karlhost01_Fahamu_Suite.html"

java -jar "selenium-server-1.0.1\selenium-server.jar" -htmlSuite "*iexplore" "http://karlhost01.sixfeetup.com:8200/" "../all_suite.html" "../log/results_ie_Karlhost01_Fahamu_Suite.html"

