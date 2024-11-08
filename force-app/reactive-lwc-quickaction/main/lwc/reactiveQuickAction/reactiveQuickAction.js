import { LightningElement, api, wire } from "lwc";
import { getRecord } from "lightning/uiRecordApi";
import { ShowToastEvent } from "lightning/platformShowToastEvent";
import createChildRecord from "@salesforce/apex/ReactiveController.createChildRecord";
import AccountIdField from "@salesforce/schema/Account.Id";
import AccountNameField from "@salesforce/schema/Account.Name";
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
        fields: ["Contact.Id","Contact.AccountId","Contact.FirstName","Contact.LastName"]
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

    @api
    set recordId(recordId) {
        this._recordId = recordId;
    }
    get recordId() {
        return this._recordId;
    }

    @api objectApiName;
    @api firstname;
    @api lastname;
    @api isEmbeddedInAura = false;
    disabled = false;

    @wire(getRecord, { recordId: "$recordId", fields: FIELDS })
    accountRecord;

    @api
    handleSave() {
        return this.handleSubmit();
    }

    @api
    async handleSaveAndNew() {
        await this.handleSubmit();
        this.resetAllValues();
    }
    // Getter to return the record data
    get recordData() {
        return this.accountRecord;
    }

    handleChange(event) {
        let val = event.target.value;
        this[event.target.dataset.id] = val;
    }

    async handleSubmit(event) {
        const { error, recId } = await createChildRecord({
            objectApiName: "Contact",
            fields: {
                FirstName: this.firstname,
                LastName: this.lastname,
                AccountId: this.recordId
            }
        });
        if (error) {
            // Display a toast notification
            this.dispatchEvent(
                new ShowToastEvent({
                    title: "Error creating child record",
                    message: error.body.message,
                    variant: "error"
                })
            );
        } else {
            this.sendCloseEvents(recId);
        }
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
        if (!this.isEmbeddedInAura) {
            // Native LWC - not embedded in Aura
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
    // createChildRecord(childObjectApiName, fields) {
    //     createChildRecord({ objectApiName: childObjectApiName, fields: fields })
    //         .then((recId) => {
    //             this.sendCloseEvents(recId);
    //         })
    //         .catch((error) => {
    //             // Display a toast notification
    //             this.dispatchEvent(
    //                 new ShowToastEvent({
    //                     title: "Error creating child record",
    //                     message: error.body.message,
    //                     variant: "error"
    //                 })
    //             );
    //         });
    // }
}
