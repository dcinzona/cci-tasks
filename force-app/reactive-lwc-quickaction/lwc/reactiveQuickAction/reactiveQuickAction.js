import { LightningElement, api, wire } from "lwc";
import { getRecord, notifyRecordUpdateAvailable } from "lightning/uiRecordApi";
import { ShowToastEvent } from "lightning/platformShowToastEvent";
import createChildRecord from "@salesforce/apex/ReactiveController.createChildRecord";
import AccountIdField from "@salesforce/schema/Account.Id";
import AccountNameField from "@salesforce/schema/Account.Name";
import { RefreshEvent } from "lightning/refresh";
import { CurrentPageReference } from "lightning/navigation";
import { CloseActionScreenEvent } from "lightning/actions";
import { refreshApex } from "@salesforce/apex";
// ------- ZK: only added this import below
import { getRelatedListRecords } from "lightning/uiRelatedListApi";

const FIELDS = [AccountIdField, AccountNameField];

export default class ReactiveQuickAction extends LightningElement {
    // ----- ZK: added this related list wire
    error;
    records = [];
    contactData;

    @wire(getRelatedListRecords, {
        parentRecordId: "$recordId",
        relatedListId: "Contacts",
        fields: ["Contact.Id"]
    })
    listInfo(result) {
        this.contactData = result;
        if (result.data) {
            this.records = result.data.records;
            this.error = undefined;
        } else if (result.error) {
            this.error = result.error;
            this.records = undefined;
        }
    }

    get hasNoRecords() {
        return this.records?.length === 0;
    }
    // -----

    @api recordId;
    @api objectApiName;
    @api firstname;
    @api lastname;
    @api isEmbeddedInAura = false;
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
        console.log("sendCloseEvents(result) => ", result);
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
        // Close the action screen
        console.log("isEmbeddedInAura", this.isEmbeddedInAura);
        console.log("this.recordId", this.recordId);
        if (!this.isEmbeddedInAura) {
            // TRIED EVERYTHING TO GET THIS TO WORK
            // Refresh the parent record
            // Notify LDS that you've changed the record outside its mechanisms

            // ------ ZK: just needed to call refreshApex on the related list wire
            refreshApex(this.contactData).then(() => {
                try {
                    console.log("refreshApex success with getRelatedListRecords wire");
                    this.dispatchEvent(new CloseActionScreenEvent());
                } catch (error) {
                    console.log("error", error);
                    this.dispatchEvent(new CloseActionScreenEvent());
                }
            });
        } else {
            // Fire the custom event (this is for the AURA wrapper to refresh the UI)
            const doneEvent = new CustomEvent("processcomplete", {
                detail: { result: result }
            });
            this.dispatchEvent(doneEvent);
        }
    }

    // Method to create the child record
    createChildRecord(childObjectApiName, fields) {
        createChildRecord({ objectApiName: childObjectApiName, fields: fields })
            .then((recId) => {
                this.sendCloseEvents(recId);
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
