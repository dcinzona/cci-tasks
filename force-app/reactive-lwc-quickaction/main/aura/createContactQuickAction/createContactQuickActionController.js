({
    executeRefresh: function (component, event) {
        console.log("executeRefresh event");
        $A.get("e.force:refreshView").fire();
        // Close the action panel
        var dismissActionPanel = $A.get("e.force:closeQuickAction");
        dismissActionPanel.fire();
    }
});
