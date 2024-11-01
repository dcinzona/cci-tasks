import { LightningElement, api, wire } from "lwc";
import { getRecord } from "lightning/uiRecordApi";
import { ShowToastEvent } from "lightning/platformShowToastEvent";
import createChildRecord from "@salesforce/apex/ReactiveController.createChildRecord";
import AccountIdField from "@salesforce/schema/Account.Id";
import AccountNameField from "@salesforce/schema/Account.Name";
import { RefreshEvent } from "lightning/refresh";
import { CurrentPageReference } from "lightning/navigation";

const FIELDS = [AccountIdField, AccountNameField];

export default class ReactiveQuickAction extends LightningElement {
    @api recordId;
    @api objectApiName;
    @api firstname;
    @api lastname;
    disabled = false;

    @wire(getRecord, { recordId: "$recordId", fields: FIELDS })
    accountRecord;

    @wire(CurrentPageReference)
    pageRef;

    get pageRefString() {
        return JSON.stringify(this.pageRef);
    }
    // Getter to return the record data
    get recordData() {
        return this.accountRecord;
    }

    handleChange(event) {
        let val = event.target.value;
        this[event.target.dataset.id] = val;
    }

    handleSubmit(event) {
        // Create the child record
        this.createChildRecord("Contact", {
            FirstName: this.firstname,
            LastName: this.lastname,
            AccountId: this.recordId
        });
    }

    handleCancel(event) {
        this.sendCloseEvents("cancel");
    }

    sendCloseEvents(result) {
        console.log("sendCloseEvents", result);
        if (result !== "cancel") {
            // Display a toast notification
            this.dispatchEvent(
                new ShowToastEvent({
                    title: "Success",
                    message: "Child record created",
                    variant: "success"
                })
            );
        }
        // Refresh the parent record
        this.dispatchEvent(new RefreshEvent());
        // Close the action screen
        // this.dispatchEvent(new CloseActionScreenEvent());
        const doneEvent = new CustomEvent("processcomplete", {
            detail: { result: result }
        });
        // Fire the custom event
        this.dispatchEvent(doneEvent);
    }

    // Method to create the child record
    createChildRecord(childObjectApiName, fields) {
        createChildRecord({ objectApiName: childObjectApiName, fields: fields })
            .then((result) => {
                this.sendCloseEvents(result);
            })
            .catch((error) => {
                // Display a toast notification
                this.dispatchEvent(
                    new ShowToastEvent({
                        title: "Error creating child record",
                        message: error.body.message,
                        variant: "error"
                    })
                );
            });
    }
}
