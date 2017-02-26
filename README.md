# MusicCampScheduler
Scheduler and dashboard applicaiton for a music camp.

This app runs the music camp scheduler site. The original target audience for this site is around 100 people for a camp around 1 week long. The intended model for the music camp is that people are allocated into groups like orchestras, bands, quartets, etc over several periods in a day. People can mark themselves as "absent" at least one day in advance and will not be allocated  to groups in the session. Once running, the website must be maintained by an adminstrator, and conductors to confirm groups.

A general how-to, using Heroku:
1. Create a Heroku account
2. Make a new web application and point it to this repository
3. Create a postgresql instance on your Heroku account, and link this app to it, selecting the python interpreter
4. Create environment variables in Heroku for each attribute in the top section config.xml.example, and edit their values to match your needs
5. Make copies of and edit your own config.xml.example, campers.csv.example and musiclibrary.csv.example, remove the .example extensions from them, and fill them with your own camp information
6. Start the app
7. navigate to https://YourAppNameHere.herokuapp.com/YourAdminUUIDHere/setup/. Replacing your app name and the AdminUUID you configured in your environment variable into the URL.
8. Upload your config.xml, and wait for the server to say success. If you get errors, check the log, you probably made a typo.
9. Reapeat step 8, uploading campers.csv and musiclibrary.csv one by one. You should see "Success" after each upload.
10. go to https://YourAppNameHere.herokuapp.com/YourAdminUUIDHere/useradmin/. You should see all your users and you're good to go.
11. Go to an admin user's dashboard (Not the Adminsitrator user, that user can only do database setup and nothing else) and make sure all the periods and configuration was successfully uploaded. Using the site as an admin is fairly intuitive, you create groups from scratch using the homepage "+Full Group", or go to the group scheduling page to automate scheduling for all user requests.
12. Go back to the useradmin page and check everyone's boxes with the very top checkbox. Send email invites, and you should be all good. If you do this a few days before camp starts, it gives everyone a chance to upload any extra music they are bringing, and make a few group requests so you can schedule day 1.

Enjoy! Feel free to ping me on github if you're planning on using this app. I'll be rebuilding it this year to make it a single page app and add tonnes more features, but it's usable now and works pretty well.
