var app = angular.module('Application', ['ngAnimate', 'ui.bootstrap']);

app.config(['$interpolateProvider', function ($interpolateProvider) {
    $interpolateProvider.startSymbol('{a');
    $interpolateProvider.endSymbol('a}');
}]);

app.controller('navController', function ($scope) {
    $scope.isNavCollapsed = true;
});

app.controller("scheduleController", function ($scope, $http) {

    //checks if the requested day's scheduling has not been completed
    $http.get("/user/" + getCookie('logonid') + "/isscheduled/2017-01-29/")
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
        $scope.schedule = response.data;
        angular.forEach($scope.schedule, function (value, key) {
            $scope.schedule[key].isOpen = false;
        });
        console.log('Schedule:')
        console.log($scope.schedule)
    });

    $scope.isAccordionOpen = false;
    $scope.firstname = 'Hello!'

});

