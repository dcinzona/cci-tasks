global class UserLookupFieldPicklist extends VisualEditor.DynamicPickList {
    VisualEditor.DesignTimePageContext context;
    global UserLookupFieldPicklist(VisualEditor.DesignTimePageContext context) {
        this.context = context;
    }
    global override VisualEditor.DataRow getDefaultValue() {
        return new VisualEditor.DataRow('--None--', '');
    }
    global override VisualEditor.DynamicPickListRows getValues() {
        VisualEditor.DynamicPickListRows myValues = new VisualEditor.DynamicPickListRows();
        String objectApiName = context.entityName;
        // get fields for the object
        Map<String, Schema.SObjectField> fields = Schema.getGlobalDescribe().get(objectApiName).getDescribe().fields.getMap();
        // check if the field maps to a User record
        for(Schema.SObjectField field : fields.values()) {
            Schema.DescribeFieldResult fieldDescribe = field.getDescribe();
            if(fieldDescribe.isCreateable() && fieldDescribe.isUpdateable()) {
                for(Schema.SObjectType reference : fieldDescribe.getReferenceTo()) {
                    if(reference.getDescribe().getName() == 'User') {
                        myValues.addRow(new VisualEditor.DataRow(fieldDescribe.getName(), fieldDescribe.getName()));
                    }
                }
            }
        }
        return myValues;
    }
}
