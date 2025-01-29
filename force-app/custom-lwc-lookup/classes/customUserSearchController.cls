public without sharing class customUserSearchController {

    @AuraEnabled
    public static List<LookupSearchResult> searchLookupRecords(String searchTerm, List<String> selectedIds,String sObjectName, String field, String subField,Integer maxResults) {
        List<LookupSearchResult> results = new List<LookupSearchResult>();
        
        List<User> users = new List<User>();
        if(String.isBlank(searchTerm) || searchTerm.length() < 2){
            return results;
        }

        String searchKeyName = searchTerm + '%';
        String searchKeyEmail = searchTerm + '%';
        String searchKeyEmployeeNumber = searchTerm + '%';
        Set<String> fields = getUserFieldsForQuery(subField);
        
        String query = 'SELECT '+ String.join(fields, ',') +' FROM User WHERE Id NOT IN :selectedIds AND (Name LIKE :searchKeyName OR Email LIKE :searchKeyEmail OR FederationIdentifier LIKE :searchTerm OR Username LIKE :searchKeyEmail OR EmployeeNumber LIKE :searchKeyEmployeeNumber)';
        try {
            for(User user : Database.query(query)){
                LookupSearchResult res = new LookupSearchResult();
                res.Id = user.Id;
                res.title = user.Name;
                res.subtitle = String.isNotBlank(subField) ? String.valueOf(user.get(subField)) : sObjectName;
                results.add(res);
            }

        } catch (Exception e) {
            throw new AuraHandledException(e.getMessage());
        }
        // String strQuery = 'SELECT Id, '+field + ' FROM User';
        // strQuery += ' WHERE '+field+' LIKE \'' + searchTerm + '%\' AND ';  
        // strQuery += ' Id NOT IN :selectedIds ORDER BY '+field+' LIMIT :maxResults';
        
        // List<sObject> searchResults = Database.query(strQuery);   
        // if(searchResults != NUll && !searchResults.isEmpty()){
        //     for(sObject sObj : searchResults){
        //         LookupSearchResult res = new LookupSearchResult();
        //         res.Id = sObj.Id;
        //         res.title = String.valueOf(sObj.get(field));
        //         if(String.isNotBlank(subField) && sObj.get(subField) != NULL){
        //             res.subtitle = String.valueOf(sObj.get(subField));
        //         }else{
        //             res.subtitle = sObjectName;
        //         }
        //         results.add(res);
        //     } 
        // }
        return results;        
    }

    static Set<String> getUserFieldsForQuery(String subField){
        Set<String> fields = new Set<String>('Id,Name,FirstName,LastName,Alias,ProfileId,Profile.Name,Username,IsActive,EmployeeNumber,Email,Phone,Title,Department,FederationIdentifier'.split(','));
        if(String.isNotBlank(subField)){
            fields.add(subField);
        }
        return fields;
    }

    @AuraEnabled
    public static LookupSearchResult getCurrentValueForRecord(String recordId, String userLookupField, String subField) {
        LookupSearchResult result = new LookupSearchResult();
        if(String.isBlank(recordId)){
            return result;
        }
        Id recId = (Id)recordId;
        String sObjectName = recId.getSObjectType().getDescribe().getName();
        List<sObject> searchResults = Database.query('SELECT '+userLookupField+' FROM '+sObjectName+' WHERE Id =:recordId');   
        if(searchResults != NUll && !searchResults.isEmpty()){
            sObject sObj = searchResults.get(0);
            LookupSearchResult res = new LookupSearchResult();
            Id userId = (Id)sObj.get(userLookupField);
            result.Id = userId;
            Set<String> fields = getUserFieldsForQuery(subField);
            String userQuery = 'SELECT '+ String.join(fields, ',') +' FROM User WHERE Id =:userId LIMIT 1';
            User u = Database.query(userQuery);
            result.title = u.Name + ' (' + u.Username + ')';
            if(String.isNotBlank(subField) && u.get(subField) != NULL){
                result.subtitle = String.valueOf(u.get(subField));
            }else{
                result.subtitle = u.Id;
            }
        }
        return result;        
    }
    
    @AuraEnabled
    public static LookupSearchResult getRecentlyCreatedRecord(String sObjectName, String recordId, String field, String subField) {
        LookupSearchResult result = new LookupSearchResult();
        sObjectName = 'User';
        String strQuery = 'SELECT Id, '+field + (String.isNotBlank(subField) ? ' ,'+subField : '')+' FROM '+sObjectName+' WHERE Id =:recordId LIMIT 1';
        List<sObject> searchResults = Database.query(strQuery);   
        if(searchResults != NUll && !searchResults.isEmpty()){
            sObject sObj = searchResults.get(0);
            LookupSearchResult res = new LookupSearchResult();
            result.Id = sObj.Id;
            result.title = String.valueOf(sObj.get(field));
            if(String.isNotBlank(subField) && sObj.get(subField) != NULL){
                result.subtitle = String.valueOf(sObj.get(subField));
            }else{
                result.subtitle = sObjectName;
            }
        }
        return result;        
    }
    
    public class LookupSearchResult {
        @AuraEnabled public Id id{get;set;}
        @AuraEnabled public String title{get;set;}
        @AuraEnabled public String subtitle{get;set;}
    }

}
