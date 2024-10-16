public without sharing class POC_UserSearchController {

    @AuraEnabled(cacheable=false)
    public static List<User> findUsers(String searchKey){
        List<User> users = new List<User>();
        if(String.isBlank(searchKey) || searchKey.length() < 2){
            return users;
        }

        String searchKeyName = searchKey + '%';
        String searchKeyEmail = searchKey + '%';
        String searchKeyEmployeeNumber = searchKey + '%';
        
        try {
            users = [SELECT Id, Name, FirstName, LastName, Alias, ProfileId, Profile.Name, Username, IsActive, EmployeeNumber, Email, Phone, Title, Department, FederationIdentifier FROM User WHERE Name LIKE :searchKeyName OR Email LIKE :searchKeyEmail OR FederationIdentifier LIKE :searchKey OR Username LIKE :searchKeyEmail OR EmployeeNumber LIKE :searchKeyEmployeeNumber];
        } catch (Exception e) {
            throw new AuraHandledException(e.getMessage());
        }
        return users;
    }

    @AuraEnabled(cacheable=false)
    public static List<POC_PersonSearchResponse> findPeople(String searchKey){
        List<POC_PersonSearchResponse> people = new List<POC_PersonSearchResponse>();
        try {
            List<User> users = findUsers(searchKey);
            people = POC_PersonSearchResponse.fromUsers(users);
        } catch (Exception e) {
            throw new AuraHandledException(e.getMessage());
        } 
        return people;
    }

    @AuraEnabled(cacheable=false)
    public static List<POC_PersonSearchResponse> upsertPeople(List<POC_PersonSearchResponse> people){
        List<POC_PersonSearchResponse> updatedPeople = new List<POC_PersonSearchResponse>();
        try {
            List<User> users = POC_PersonSearchResponse.checkExistingUsers(people);
            database.upsert(users, true);
            updatedPeople = POC_PersonSearchResponse.fromUsers(users);
        } catch (Exception e) {
            throw new AuraHandledException(e.getMessage());
        }
        return updatedPeople;
    }
}