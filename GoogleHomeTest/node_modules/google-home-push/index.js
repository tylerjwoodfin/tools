"use strict";

const GoogleCastClient = require("castv2-client").Client;
const DefaultMediaReceiver = require("castv2-client").DefaultMediaReceiver;
const mdns = require("mdns");
const browser = mdns.createBrowser(mdns.tcp("googlecast"));
const googleTTS = require("google-tts-api");
const isIp = require("is-ip");

class GoogleHome {
  constructor(deviceIdentifier, options = {}) {
    this.device = {};

    if (isIp(deviceIdentifier)) {
      this.device.ip = deviceIdentifier;
    } else {
      this.device.name = deviceIdentifier;
    }
    this.device.identifier = deviceIdentifier;

    this.options = options;

    this.options.language =
      this.options.language === undefined ? "en" : options.language;

    this.options.speed =
      this.options.speed === undefined ? 1 : options.speed;
    
    this.options.timeout =
      this.options.timeout === undefined ? 5000 : options.timeout;
  }

  searchDevice(name = this.device.name) {
    return new Promise((resolve, reject) => {
      browser.start();

      browser.on("serviceUp", (service) => {
        browser.stop();

        // Only use the first IP address in the array
        const address = service.addresses[0];
        console.log(
          `Device ${service.txtRecord.fn} at ${address}:${service.port} found`
        );

        if (service.txtRecord.fn.includes(name)) {
          resolve(address);
        }
      });

      setTimeout(() => {
        reject(`.searchDevice(): Search timeout`);
      }, this.options.timeout);
    });
  }

  async speak(message, language) {
    if (!message) {
      console.error(".speak(): The text to speak cannot be empty");
      return false;
    }

    return new Promise((resolve, reject) => {
      googleTTS(message, language ? language : this.options.language, this.options.speed)
        .then((url) => {
          this.push(url).then(resolve).catch(reject);
        })
        .catch(reject);
    }).catch((reject) => {
      console.error(reject);
    });
  }

  push(url) {
    return new Promise(async (resolve, reject) => {
      if (this.device.ip === undefined || !isIp(this.device.ip)) {
        try {
          this.device.ip = await this.searchDevice();
        } catch (err) {
          return reject(err);
        }
      }

      const client = new GoogleCastClient();
      client.connect(this.device.ip, () => {
        client.launch(DefaultMediaReceiver, (err, player) => {
          const media = {
            contentId: url,
            contentType: "audio/mp3",
            streamType: "BUFFERED",
          };

          player.load(media, { autoplay: true }, (err, status) => {
            client.close();
            resolve(status);
            console.log(`Pushed to device at ${this.device.ip}`);
          });
        });
      });

      client.on("error", (err) => {
        reject(`Google Cast Client error:\n${err}`);
        client.close();
      });
    });
  }
}

module.exports = GoogleHome;
