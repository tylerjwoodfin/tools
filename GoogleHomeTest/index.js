const http = require('http');
const express = require('express');

const hostname = '127.0.0.1';
const port = 3000;
const app = express();
const router = express.Router();

const GoogleHome = require("google-home-push");

// Pass the name or IP address of your device
const myHome = new GoogleHome("192.168.1.225");

myHome.speak("Hello Tyler!");

function runServer() {
  app.set('view engine', 'ejs');

  router.get('/test', function(req, res) {
    console.log("Test");
    myHome.speak("Looks good.");
    res.end("Hello!!");
  });

  router.get('/', function(req, res) {
    console.log("FirstPage");
    myHome.speak("Looks blank.");
    res.end("Firstly");
  });

  // make the app listen for routes
  app.use('/', router);
  app.listen(process.env.port || 3000);

  console.log('Running at Port 3000');

  // res.end("Hello World");
}

setTimeout(runServer,3000);