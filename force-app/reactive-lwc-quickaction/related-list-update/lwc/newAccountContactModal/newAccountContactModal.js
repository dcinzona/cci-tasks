import { api } from "lwc";
import LightningModal from "lightning/modal";

export default class NewAccountContactModal extends LightningModal {
    @api label;
    @api recordId;

    handleCancel() {
        this.close({
            buttonName: "cancel"
        });
    }

    async handleSaveAndNew() {
        await this.template.querySelector("c-reactive-quick-action").handleSaveAndNew();
    }

    async handleSave() {
        const createdRecordId = await this.template.querySelector("c-reactive-quick-action").handleSave();
        this.close({
            buttonName: "save",
            recordId: createdRecordId
        });
    }
}
