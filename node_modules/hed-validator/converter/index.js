const converter = require('./converter')
const schema = require('./schema')

module.exports = {
  buildSchema: schema.buildSchema,
  convertHedStringToShort: converter.convertHedStringToShort,
  convertHedStringToLong: converter.convertHedStringToLong,
}
