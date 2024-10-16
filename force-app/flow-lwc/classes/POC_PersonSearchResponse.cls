public without sharing class POC_PersonSearchResponse {
    
    @AuraEnabled
    public string name {get; set;}
    @AuraEnabled
    public string username {get; set;}
    @AuraEnabled
    public string firstname {get; set;}
    @AuraEnabled
    public string lastname {get; set;}
    @AuraEnabled
    public string email {get; set;}
    @AuraEnabled
    public string phone {get; set;}
    @AuraEnabled
    public string title {get; set;}
    @AuraEnabled
    public string department {get; set;}
    @AuraEnabled
    public string federationid {get; set;}
    @AuraEnabled
    public string sfid {get; set;}
    @AuraEnabled
    public Boolean isActive {get {
        return String.isNotBlank(this.sfid);
    }}

    public POC_PersonSearchResponse(){
        this.name = '';
        this.email = '';
        this.phone = '';
        this.title = '';
        this.department = '';
        this.federationid = '';
        this.sfid = null;
    }

    public POC_PersonSearchResponse(User user){
        this.name = user.Name;
        this.username = user.Username;
        this.firstname = user.FirstName;
        this.lastname = user.LastName;
        this.email = user.Email;
        this.phone = user.Phone;
        this.title = user.Title;
        this.department = user.Department;
        this.federationid = user.FederationIdentifier;
        this.sfid = user.Id;
    }

    private static Id defaultProfileId;
    public static Id getDefaultProfileId(){
        if(defaultProfileId == null){
            defaultProfileId = [SELECT Id FROM Profile WHERE Name = 'Standard User'].Id;
        }
        return defaultProfileId;
    }

    public User toUser(){
        User user = new User();
        user.Email = this.email;
        user.Phone = this.phone;
        user.Title = this.title;
        user.Department = this.department;
        user.FederationIdentifier = this.federationid;
        user.Id = this.sfid;
        user.FirstName = this.firstname;
        user.LastName = this.lastname;
        user.Username = this.username;
        String sandboxName = getSandboxName();
        if(sandboxName != null){
            user.Username += '.' + sandboxName;
        }
        user.IsActive = this.isActive;
        return user;
    }

    public User toCreateUser(){
        User user = toUser();
        user.ProfileId = getDefaultProfileId();
        user.Alias = this.firstname.substring(0,1) + this.lastname.substring(0,1) + this.randomNumberForAlias();
        user.TimeZoneSidKey = 'America/New_York';
        user.LocaleSidKey = 'en_US';
        user.EmailEncodingKey = 'UTF-8';
        user.LanguageLocaleKey = 'en_US';
        user.CommunityNickname = this.username;
        return user;
    }

    private Integer randomNumberForAlias(){
        return Integer.valueOf(Math.random() * 10000);
    }

    public static List<POC_PersonSearchResponse> fromUsers(List<User> users){
        List<POC_PersonSearchResponse> people = new List<POC_PersonSearchResponse>();
        for(User user : users){
            people.add(new POC_PersonSearchResponse(user));
        }
        return people;
    }

    public static List<User> toUsers(List<POC_PersonSearchResponse> people){
        List<User> users = new List<User>();
        for(POC_PersonSearchResponse person : people){
            users.add(person.toUser());
        }
        return users;
    }

    private static String getSandboxName(){
        System.Domain d = System.DomainParser.parse(URL.getOrgDomainUrl());
        return d.getSandboxName();
    }

    public static List<POC_PersonSearchResponse> checkExistingUsersToPeople(List<User> peopleToCheck){
        return fromUsers(checkExistingUsers(peopleToCheck));
    }

    public static List<User> checkExistingUsers(List<POC_PersonSearchResponse> peopleToCheck){
        return checkExistingUsers(toUsers(peopleToCheck));
    }

    public static List<User> checkExistingUsers(List<User> usersToCheck){
        Map<String, User> userByFedIdMap = new Map<String, User>();
        Map<String, User> userByUsername = new Map<String, User>();
        Map<String, List<User>> userByEmail = new Map<String, List<User>>(); // can have multiple users with the same email

        for(User user : usersToCheck){
            if(String.isBlank(user.Id)){
                if(String.isNotBlank(user.Username)){
                    userByUsername.put(user.Username, user);
                }
                if(String.isNotBlank(user.Email)){
                    String email = user.Email;
                    if (email.endsWith('.invalid')) {
                        email = email.substringBeforeLast('.');                        
                    }
                    String emailInvalid = email + '.invalid';
                    if(!userByEmail.containsKey(email)){
                        userByEmail.put(email, new List<User>());
                    }
                    userByEmail.get(email).add(user);
                    if(!userByEmail.containsKey(emailInvalid)){
                        userByEmail.put(emailInvalid, new List<User>());
                    }
                    userByEmail.get(emailInvalid).add(user);
                }
                if(String.isNotBlank(user.FederationIdentifier)){
                    userByFedIdMap.put(user.FederationIdentifier, user);
                }
            }
        }

        List<User> existingUsers = runSOQLQuery(userByFedIdMap, userByUsername, userByEmail);

        for(User existingUser : existingUsers){
            for(User targetUser : usersToCheck){
                if(targetUser.Id != null){
                    continue;
                }
                if(checkUniqueFields(targetUser, existingUser)){
                    copyExistingUserFieldValuesToUser(targetUser, existingUser);
                    break; // no need to check for other conditions
                }
                if(checkForWhenEmailsMatch(targetUser, existingUser)){
                    copyExistingUserFieldValuesToUser(targetUser, existingUser);
                    continue;
                }
            }
        }

        return usersToCheck;
    }

    private static Boolean checkUniqueFields(User targetUser, User existingUser){
        return checkFedIdMatch(targetUser, existingUser) || checkUsernameMatch(targetUser, existingUser);
    }

    private static Boolean checkFedIdMatch(User targetUser, User existingUser){
        return String.isNotBlank(targetUser.FederationIdentifier) && targetUser.FederationIdentifier.equals(existingUser.FederationIdentifier);
    }

    private static Boolean checkUsernameMatch(User targetUser, User existingUser){
        return String.isNotBlank(targetUser.Username) && targetUser.Username.equalsIgnoreCase(existingUser.Username);
    }

    // if the user has the same first and last name, or the same last name and email, then we should update the user
    private static Boolean checkForWhenEmailsMatch(User user, User existingUser){
        return (user.FirstName.equalsIgnoreCase(existingUser.FirstName) &&
        String.isNotBlank(user.FirstName) &&
        user.LastName.equalsIgnoreCase(existingUser.LastName)) || 
        (user.LastName.equalsIgnoreCase(existingUser.LastName) &&
            (user.Email.equalsIgnoreCase(existingUser.Email) || 
                user.Email.equalsIgnoreCase(existingUser.Email + '.invalid')));
    }

    private static List<User> runSOQLQuery(Map<String, User> userByFedIdMap, Map<String, User> userByUsername, Map<String, List<User>> userByEmail){
        List<User> existingUsers = new List<User>();
        if(!userByFedIdMap.isEmpty() || !userByUsername.isEmpty() || !userByEmail.isEmpty()){
            String queryString = 'SELECT Id, Username, ProfileId, IsActive, EmployeeNumber, Email, Phone, Title, Department, Location, FederationIdentifier FROM User WHERE ';
            List<String> whereClauses = new List<String>();
            if(!userByFedIdMap.isEmpty()){
                whereClauses.add('FederationIdentifier IN :userByFedIdMap.keySet()');
            }
            if(!userByUsername.isEmpty()){
                whereClauses.add('Username IN :userByUsername.keySet()');
            }
            if(!userByEmail.isEmpty()){
                whereClauses.add('Email IN :userByEmail.keySet()');
            }
            queryString += String.join(whereClauses, ' OR ');
            existingUsers = Database.query(queryString);
        }
        return existingUsers;
    }

    private static User copyExistingUserFieldValuesToUser(User targetUser, User existingUser ){
        if(targetUser.Id != null){
            return targetUser;
        }
        targetUser.Id = existingUser.Id;
        targetUser.FirstName = existingUser.FirstName;
        targetUser.LastName = existingUser.LastName;
        targetUser.ProfileId = String.isBlank(targetUser.ProfileId) ? existingUser.ProfileId : targetUser.ProfileId;
        targetUser.IsActive = existingUser.IsActive;
        targetUser.EmployeeNumber = String.isNotBlank(existingUser.EmployeeNumber) ? existingUser.EmployeeNumber : targetUser.EmployeeNumber;
        targetUser.Email = existingUser.Email;
        targetUser.FederationIdentifier = existingUser.FederationIdentifier;
        return targetUser;
    }
}