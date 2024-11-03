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

const FIELDS = [AccountIdField, AccountNameField];

export default class ReactiveQuickAction extends LightningElement {
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
            refreshApex(this.accountRecord).then(() => {
                try {
                    let records = [{ recordId: this.recordId }, { recordId: result }];
                    console.log("records for update", JSON.stringify(records));
                    notifyRecordUpdateAvailable(records).then(() => {
                        console.log("notifyRecordUpdateAvailable done");
                        this.dispatchEvent(new RefreshEvent());
                        this.dispatchEvent(new CloseActionScreenEvent());
                    });
                } catch (error) {
                    console.log("error", error);
                    this.dispatchEvent(new RefreshEvent());
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
                //await this.refreshTab("success");
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

    // WORKSPACE / CONSOLE CHECK
    refreshTab(msg) {
        this.invokeWorkspaceAPI("isConsoleNavigation").then((isConsole) => {
            if (isConsole) {
                this.invokeWorkspaceAPI("getFocusedTabInfo").then((focusedTab) => {
                    this.invokeWorkspaceAPI("refreshTab", {
                        tabId: focusedTab.tabId
                    }).then(async (response) => {
                        this.sendCloseEvents(msg);
                    });
                });
            } else {
                // not console, just do a refresh
                this.sendCloseEvents(msg);
            }
        });
    }

    invokeWorkspaceAPI(methodName, methodArgs) {
        return new Promise((resolve, reject) => {
            const apiEvent = new CustomEvent("internalapievent", {
                bubbles: true,
                composed: true,
                cancelable: false,
                detail: {
                    category: "workspaceAPI",
                    methodName: methodName,
                    methodArgs: methodArgs,
                    callback: (err, response) => {
                        if (err) {
                            return reject(err);
                        } else {
                            return resolve(response);
                        }
                    }
                }
            });
            this.dispatchEvent(apiEvent);
            window.dispatchEvent(apiEvent);
        });
    }
}
