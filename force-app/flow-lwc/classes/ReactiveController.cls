public with sharing class ReactiveController {
    @AuraEnabled(cacheable=false)
    public static Object createChildRecord(String objectApiName, Map<String, Object> fields) {
        try {
            // Create the child record
            SObject childRecord = Schema.getGlobalDescribe().get(objectApiName).newSObject();
            System.debug('fields: ' + JSON.serializePretty(fields));
            for (String fieldName : fields.keySet()) {
                childRecord.put(fieldName, fields.get(fieldName));
            }
            return JSON.serialize(Database.insert(childRecord));
        } catch (Exception e) {
            throw new AuraHandledException(e.getMessage());
        }
    }    
    
    @AuraEnabled(cacheable=false)
    public static List<Object> createChildRecords(String objectApiName, List<Map<String, Object>> fields) {
        try {
            List<SObject> childRecords = new List<SObject>();
            for(Map<String, Object> record : fields) {
                // Create the child record
                SObject childRecord = Schema.getGlobalDescribe().get(objectApiName).newSObject();
                System.debug('fields: ' + JSON.serializePretty(record));
                for (String fieldName : record.keySet()) {
                    childRecord.put(fieldName, record.get(fieldName));
                }
                childRecords.add(childRecord);
            }
            return Database.insert(childRecords);
        } catch (Exception e) {
            throw new AuraHandledException(e.getMessage());
        }
    }

    @AuraEnabled(cacheable=false)
    public static Object updateChildRecord(Map<String, Object> fields) {
        try {
            // Create the child record
            Id recordId = fields.containsKey('Id') ? (Id)fields.get('Id') : fields.containsKey('id') ? (Id)fields.get('id') : fields.containsKey('ID') ? (Id)fields.get('ID') : null;
            if(recordId == null) {
                throw new AuraHandledException('Record Id is required');
            }
            SObject childRecord = recordId.getSObjectType().newSObject(recordId);
            System.debug('fields: ' + JSON.serializePretty(fields));
            for (String fieldName : fields.keySet()) {
                childRecord.put(fieldName, fields.get(fieldName));
            }

            return Database.update(childRecord);
        } catch (Exception e) {
            throw new AuraHandledException(e.getMessage());
        }
    }

    @AuraEnabled(cacheable=false)
    public static List<Object> updateChildRecords(List<Map<String, Object>> records) {
        try {
            List<SObject> childRecords = new List<SObject>();
            for(Map<String, Object> fields : records) {
                // Create the child record
                Id recordId = fields.containsKey('Id') ? (Id)fields.get('Id') : fields.containsKey('id') ? (Id)fields.get('id') : fields.containsKey('ID') ? (Id)fields.get('ID') : null;
                if(recordId != null) {
                    SObject childRecord = recordId.getSObjectType().newSObject(recordId);
                    System.debug('fields: ' + JSON.serializePretty(fields));
                    for (String fieldName : fields.keySet()) {
                        childRecord.put(fieldName, fields.get(fieldName));
                    }

                    childRecords.add(childRecord);
                } else {
                    System.debug('Record Id is required for record: ' + fields);
                }
            }

            return Database.update(childRecords);
        } catch (Exception e) {
            throw new AuraHandledException(e.getMessage());
        }
    }
}
