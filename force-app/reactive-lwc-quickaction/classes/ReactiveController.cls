public with sharing class ReactiveController {
    @AuraEnabled(cacheable=false)
    public static Id createChildRecord(String objectApiName, Map<String, Object> fields) {
        try {
            // Create the child record
            SObject childRecord = Schema.getGlobalDescribe().get(objectApiName).newSObject();
            System.debug('fields: ' + JSON.serializePretty(fields));
            for (String fieldName : fields.keySet()) {
                childRecord.put(fieldName, fields.get(fieldName));
            }
            insert childRecord;
            return childRecord.Id;
        } catch (Exception e) {
            throw new AuraHandledException(e.getMessage());
        }
    }
}
