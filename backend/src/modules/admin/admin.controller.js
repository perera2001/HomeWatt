const adminService = require('./admin.service');

const home = (req, res) => {
  res.status(200).json({
    message: adminService.getHomeMessage()
  });
};

const getUsers = async (req, res, next) => {
  try {
    const users = await adminService.getAllUsers();

    res.status(200).json({
      users
    });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  home,
  getUsers
};
