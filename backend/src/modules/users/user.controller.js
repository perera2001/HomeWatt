const userService = require('./user.service');

const home = (req, res) => {
  res.status(200).json({
    message: userService.getHomeMessage()
  });
};

module.exports = {
  home
};
