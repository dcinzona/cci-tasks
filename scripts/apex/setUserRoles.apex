delete [SELECT Id FROM UserRole];
UserRole ur = new UserRole(Name = 'CEO');
insert ur;
update new User(Id = UserInfo.getUserId(), UserRoleId = ur.Id);