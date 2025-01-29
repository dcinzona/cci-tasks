global  class pocBuilderSobjectSelector extends VisualEditor.DynamicPickList{

    VisualEditor.DesignTimePageContext context;

    global pocBuilderSobjectSelector(VisualEditor.DesignTimePageContext context) {
       this.context = context;
    }

    global override VisualEditor.DataRow getDefaultValue(){
        // get entity name
        String objectApiName = context.entityName;
        if (objectApiName == null) {
            return new VisualEditor.DataRow('Account', 'Account');
        }
        return new VisualEditor.DataRow(objectApiName, objectApiName);
    }

    global override VisualEditor.DynamicPickListRows getValues() {

        VisualEditor.DynamicPickListRows myValues = new VisualEditor.DynamicPickListRows();
        // get entity name
        String objectApiName = context.entityName;
        if (objectApiName == null) {
            // get list of salesforce sobjects and api names
            Map<String, Schema.SObjectType> gd = Schema.getGlobalDescribe();
            List<VisualEditor.DataRow> rows = new List<VisualEditor.DataRow>();
            for (String sobj : gd.keySet()) {
                myValues.addRow(new VisualEditor.DataRow(sobj, sobj));
            }
        } else {
            myValues.addRow(new VisualEditor.DataRow(objectApiName, objectApiName));
        }
        return myValues;
    }
}
