global class UserObjectFieldPicklist extends VisualEditor.DynamicPickList {
    VisualEditor.DesignTimePageContext context;
    global UserObjectFieldPicklist(VisualEditor.DesignTimePageContext context) {
        this.context = context;
    }
    global override VisualEditor.DataRow getDefaultValue() {
        return new VisualEditor.DataRow('Id', 'Id');
    }
    global override VisualEditor.DynamicPickListRows getValues() {
        VisualEditor.DynamicPickListRows myValues = new VisualEditor.DynamicPickListRows();
        String objectApiName = 'User';
        // get fields for the object
        Map<String, Schema.SObjectField> fields = Schema.getGlobalDescribe().get(objectApiName).getDescribe().fields.getMap();
        // return the field label and name
        for(Schema.SObjectField field : fields.values()) {
            Schema.DescribeFieldResult fieldDescribe = field.getDescribe();
            if(fieldDescribe.isCreateable() && fieldDescribe.isUpdateable()) {
                myValues.addRow(new VisualEditor.DataRow(fieldDescribe.getLabel(), fieldDescribe.getName()));
            }
        }
        return myValues;
    }
}
