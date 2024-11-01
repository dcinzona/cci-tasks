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

    @AuraEnabled(cacheable=false)
    public static List<Id> createChildRecords(
        String parentLookupFieldApiName,
        String childObjectApiName,
        List<Map<String, Object>> fields
    ) {
        try {
            // Create the child record
            List<SObject> childRecords = new List<SObject>();
            SObject childRecord = Schema.getGlobalDescribe().get(childObjectApiName).newSObject();
            for (Map<String, Object> field : fields) {
                for (String fieldName : field.keySet()) {
                    childRecord.put(fieldName, field.get(fieldName));
                }
                childRecords.add(childRecord);
            }
            insert childRecords;
            List<Id> childRecordIds = new List<Id>();
            for (SObject record : childRecords) {
                childRecordIds.add(record.Id);
            }
            return childRecordIds;
        } catch (Exception e) {
            throw new AuraHandledException(e.getMessage());
        }
    }
}
