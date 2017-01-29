app.controller("homeController", function ($scope, $http) {

    //checks if the requested day's scheduling has not been completed
    $http.get("/user/" + getCookie('logonid') + "/getschedule/2017-01-29/")
    .then(function (response) {
        $scope.unscheduled = response.data;
    });

    //gets the details of the logged in user
    $http.get("/user/" + getCookie('logonid') + "/getuser/")
    .then(function (response) {
        console.log('This user:')
        console.log(response.data)
        $scope.thisuser = response.data;
    });

    //grabs the user's schedule for the current day
    $http.get("/user/" + getCookie('logonid') + "/getschedule/2017-01-29/")
    .then(function (response) {
        console.log('Schedule:')
        console.log(response.data)
        $scope.schedule = response.data;
    });


    $scope.firstname = 'Hello!'
});