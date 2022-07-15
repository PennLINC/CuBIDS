const fs = require('fs')
const request = require('then-request')

/**
 * Read a local file.
 *
 * @param {string} fileName The file path.
 * @return {Promise<unknown>} A promise with the file contents.
 */
function readFile(fileName) {
  return new Promise(resolve => {
    fs.readFile(fileName, 'utf8', function(err, data) {
      process.nextTick(function() {
        return resolve(data)
      })
    })
  })
}

/**
 * Read a remote file using HTTPS.
 *
 * @param {string} url The remote URL.
 * @return {Promise<unknown>} A promise with the file contents.
 */
function readHTTPSFile(url) {
  return request('GET', url).then(res => {
    return res.getBody()
  })
}

module.exports = {
  readFile: readFile,
  readHTTPSFile: readHTTPSFile,
}
