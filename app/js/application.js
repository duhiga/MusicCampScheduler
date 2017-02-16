var app = angular.module('Application', ['ngAnimate', 'ui.bootstrap']);

app.config(['$interpolateProvider', function ($interpolateProvider) {
    $interpolateProvider.startSymbol('{a');
    $interpolateProvider.endSymbol('a}');
}]);

app.controller('navController', function ($scope) {
    $scope.isNavCollapsed = true;
});

app.controller("scheduleController", function ($scope, $http, $filter, $log, $document) {

    var today = $filter('date')(new Date(), 'yyyy-MM-dd');
    console.log('Today is:');
    console.log(today);

    //gets the details of the logged in user
    $http.get("/user/" + getCookie('logonid') + "/getuser/")
    .then(function (response) {
        console.log('This user:')
        console.log(response.data)
        $scope.thisuser = response.data;
        $scope.thisuser.arrival = Date.parse($scope.thisuser.arrival);
        $scope.thisuser.departure = Date.parse($scope.thisuser.departure);
    });

    //grabs the user's schedule for the current day
    $http.get("/user/" + getCookie('logonid') + "/getschedule/" + today + "/")
    .then(function (response) {
        $scope.unscheduled = response.data.unscheduled;
        console.log('Unscheduled: ' + $scope.unscheduled)
        $scope.schedule = response.data.schedule;
        angular.forEach($scope.schedule, function (value, key) {
            $scope.schedule[key].isOpen = false;
            $scope.schedule[key].starttime = Date.parse($scope.schedule[key].starttime);
            $scope.schedule[key].endtime = Date.parse($scope.schedule[key].endtime);
        });
        console.log('Schedule:');
        console.log($scope.schedule);
    });
});

app.controller('modalController', function ($scope, $uibModal, $log) {
    $scope.openModal = openModal;
    $scope.people = [
        'Fred',
        'Jim',
        'Bob'
    ];
    $scope.body = "This is the body"
    $scope.title = "Hello"

    function openModal(person) {
        var modalInstance = $uibModal.open({
            templateUrl: 'modalContent.html',
            controller: 'modalInstanceCtrl',
            controllerAs: '$ctrl',
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            size: "lg",
            resolve: {
                title: function () { return $scope.title },
                body: function () { return $scope.body }
            }
        });

        modalInstance.result.then(function (selectedItem) {
            $scope.selected = selectedItem;
        }, function () {
            $log.info('Modal dismissed at: ' + new Date());
        });
    }
});

app.controller('modalInstanceCtrl', function ($uibModalInstance, $log, title, body) {
    var $ctrl = this;
    $ctrl.title = title;
    $ctrl.body = body;
    $ctrl.selected = "Something...";

    $ctrl.ok = function () {
        $log.info('Clicked on OK');
        $uibModalInstance.close($ctrl.selected);
    };

    $ctrl.cancel = function () {
        $log.info('Clicked on Cancel');
        $uibModalInstance.dismiss('cancel');
    };
});

app.controller('groupModalController', function ($scope, $http, $uibModal, $log) {
    $scope.objects = {}
    $scope.init = function (groupid) {
        $http.get("/user/" + getCookie('logonid') + "/getgroup/" + groupid + "/")
        .then(function (response) {
            $scope.objects.group = response.data.group;
            $scope.objects.location = response.data.location;
            $scope.objects.period = response.data.period;
            $scope.objects.music = response.data.music;
            $scope.objects.players = response.data.players;
            $scope.objects.type = 'group'
        });
    };
    $scope.openModal = openModal;

    function openModal() {
        var modalInstance = $uibModal.open({
            templateUrl: 'groupModalContent.html',
            controller: 'modalInstanceCtrl',
            controllerAs: '$ctrl',
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            size: "lg",
            resolve: {
                objects: function () { return $scope.objects },
            }
        });

        modalInstance.result.then(function (selectedItem) {
            $scope.selected = selectedItem;
        }, function () {
            $log.info('Modal dismissed at: ' + new Date());
        });
    }
});

app.controller('modalInstanceCtrl', function ($uibModalInstance, $log, objects) {
    var $ctrl = this;
    $ctrl.objects = objects;

    $ctrl.parseDate = function (date) {
        parsedDate = Date.parse(date);
        return parsedDate
    }

    $ctrl.ok = function () {
        $log.info('Clicked on OK');
        $uibModalInstance.close($ctrl.selected);
    };

    $ctrl.cancel = function () {
        $log.info('Clicked on Cancel');
        $uibModalInstance.dismiss('cancel');
    };

    $ctrl.close = function () {
        $log.info('Clicked on Close');
        $uibModalInstance.dismiss('Close');
    };

});