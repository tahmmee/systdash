var CBFS_ROOT = '/.cbfs/list/system-test-results/'
var systestApp = angular.module('systestApp', ['ui.bootstrap']);

systestApp.config(['$httpProvider', function($httpProvider) {
        $httpProvider.defaults.useXDomain = true;
        delete $httpProvider.defaults.headers.common['X-Requested-With'];
        // XMLHttpRequest cannot load http://.... Request header field Content-Type is not allowed by Access-Control-Allow-Headers.
        delete $httpProvider.defaults.headers.common['Content-Type'];
    }
]);

function newBuildObj(){

  var emptySet = "--";
  return { selectedVersion : 'Version',
          selectedTest : 'Test',
          selectedBuild : 'Build',
          versions : null,
          tests : null,
          builds : null,
          str : null,
          isBaseline : false}
}

function filterRootDir(dirs){
  var versiondirs = []
  for (var i in dirs){
    if(dirs[i] != 'dashboard' && dirs[i] != 'reports'){
      versiondirs.push(dirs[i])
    }
  }

  return versiondirs
}
systestApp.controller('BuildSelector', function SystestCtrl($scope, $http){

  var emptySet = "--";
  $scope.baseline = newBuildObj()
  $scope.isBaseline = true
  $scope.comparisions = []
  $scope.report_ready = false
  $scope.report_status = "Compare!"
  $scope.report_icon = "fa-share"

  var buildAtIndex = function(idx){

      if (idx == undefined)
        return $scope.baseline

      return $scope.comparisions[idx]
  }

  var lsPath = function(path, cb){
    $http.get(CBFS_ROOT+path).success(function(data){
      var dirs = data['dirs']
      cb(Object.keys(dirs))
    });
  }

  var setVerisions = function(idx){
    var build = buildAtIndex(idx)
    lsPath('', function(_dirs){
      // splice non-build dirs
      build.versions = filterRootDir(_dirs)
    })
  }

  var checkReportReady = function(){
    if ($scope.baseline.str != null){
      $scope.report_ready = true
      $scope.report_status = "Report!"
      for (var i in $scope.comparisions){
        if ($scope.comparisions[i].str != null){
          $scope.report_status = "Compare!"
          $scope.report_ready = true
        }
      }
    } else {
      $scope.report_ready = false
   }
  }

  $scope.versionChange = function(version, idx){
    var build = buildAtIndex(idx)
    build.selectedVersion = version

    if(version == emptySet || !version){
      build.tests = null;
      build.builds = null;
    } else {
      lsPath(version+'/', function(_dirs){
        build.tests = _dirs
      })
    }

  }

  $scope.testChange = function(test, idx){

    var build = buildAtIndex(idx)
    var version = build.selectedVersion;
    build.selectedTest = test


    if(test == emptySet){
      build.builds = null;
    } else {
      lsPath(version+'/'+test+'/', function(_dirs){
        build.builds = _dirs
      })
    }

  }



  $scope.buildChange = function(buildstr, idx){

    var build = buildAtIndex(idx)
    var version = build.selectedVersion;
    var test = build.selectedTest;
    build.selectedBuild = buildstr

    if(buildstr != emptySet){
      var str = version+"  "+test+"  "+buildstr;
      build.str = str
    }

    checkReportReady()
  };


  $scope.addComparision = function(){
    var nextIndex = $scope.comparisions.length;
    $scope.comparisions.push(newBuildObj());
    setVerisions(nextIndex);
  };

  $scope.generateReport = function(){

    var baseline = {
      version : $scope.baseline.selectedVersion,
      test : $scope.baseline.selectedTest,
      build : $scope.baseline.selectedBuild
    }

    var comparisions = []
    for (var i in $scope.comparisions){
      var compare = $scope.comparisions[i]
      comparisions.push({
        version : compare.selectedVersion,
        test : compare.selectedTest,
        build : compare.selectedBuild
      })
    }

    var report_spec = {'baseline' : baseline,
                       'comparisions' : comparisions}

    report_spec = JSON.stringify(report_spec);
    $scope.report_icon="fa-thumbs-o-up"
    $scope.report_status = "Building..."
    $http.post('http://plum-003.hq.couchbase.com/report', report_spec)
      .success(function(url){
        $scope.report_url = url
        $scope.report_status = "Compare!"
        $scope.report_icon = "fa-share"
        console.log(url)
      });
  };

  setVerisions()
  $scope.addComparision()

});
