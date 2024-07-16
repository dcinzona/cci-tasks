for(Account a: [SELECT Id FROM Account LIMIT 500]){
    ConnectApi.Subscription subscriptionToRecord = ConnectApi.ChatterUsers.follow(null, 'me', a.Id);
}