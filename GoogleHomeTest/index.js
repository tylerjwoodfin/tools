const http = require('http');

const hostname = '127.0.0.1';
const port = 3000;

const GoogleHome = require("google-home-push");

// Pass the name or IP address of your device
const myHome = new GoogleHome("192.168.1.225");

myHome.speak("Hello Tyler! Don't forget to post this on Instagram.");

const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.end('Hello World');
});

server.listen(port, hostname, () => {
  console.log(`Server running at http://${hostname}:${port}/`);
});
