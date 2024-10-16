import { LightningElement, api } from 'lwc';
import { ShowToastEvent } from 'lightning/platformShowToastEvent';
import findUsers from '@salesforce/apex/POC_UserSearchController.findUsers';
import { FlowAttributeChangeEvent } from "lightning/flowSupport";

const columns = [
    { label: 'Name', fieldName: 'Name' },
    { label: 'Email', fieldName: 'Email', type: 'email' },
    { label: 'Profile', fieldName: 'ProfileName' },
    { label: 'Username', fieldName: 'Username' },
];

export default class PocUserSearchComponent extends LightningElement {
    columns = columns;
    @api selectedUsers;
    @api selectedRows;
    @api searchResults;
    @api searchKey;
    @api maxRowSelection = 5;
    @api error;
    @api isLoading;
    @api showTable = false;
    @api selectedData = [];
    @api currentlySelectedData = [];

    connectedCallback() {
        console.log('Selected users:', JSON.stringify(this.selectedUsers));
        this.searchResults = [];
        this.selectedData = this.selectedUsers || [];
        this.currentlySelectedData = this.selectedData.map(row => row.Id);
        this.refreshViews();
    }

    handleRowSelection(event) {
        this.error = null;
        try {            
            console.log('Row selection event:', JSON.stringify(event.detail));
            let arr = this.selectedData.map(row => row.Id);
            //this.currentlySelectedData = event.detail.selectedRows.map(row => row.Id);
            switch (event.detail.config.action) {
                case 'selectAllRows':
                    this.searchResults.forEach(row => {
                        if (arr.indexOf(row.Id) === -1) {
                            this.selectedData.push(row);
                        }
                    });
                    break;
                case 'deselectAllRows':
                    this.searchResults.forEach(row => {
                        this.selectedData = this.selectedData.filter(r => r.Id !== row.Id);
                    });
                    break; 
                case 'rowSelect':
                    if (arr.indexOf(event.detail.config.value) === -1) {
                        this.selectedData.push(this.searchResults.find(row => row.Id === event.detail.config.value));
                    }
                    break;
                case 'rowDeselect':
                    this.selectedData = this.selectedData.filter(row => {
                        return row.Id !== event.detail.config.value;
                    });
                    break;
                default:
                    break;
            }
            console.log('Selected data:', JSON.stringify(this.selectedData));
            this.refreshViews();
        } catch (error) {
            this.error = error.body.message;
        }
    }

    debounceTimeout;
    searchButtonClick(event) {
        this.searchUsers(this.searchKey);
    }

    handleSearchKeyChange(event) {
        this.searchKey = event.target.value;
        if (this.debounceTimeout) {
            window.clearTimeout(this.debounceTimeout);
        }
        if (this.searchKey.length >= 2) {
            this.debounceTimeout = setTimeout(() => {
                this.searchUsers(this.searchKey);
            }, 300, this);
        } else {
            this.showTable = false;
        }
    }

    get showNoResults() {
        return this.searchResults && this.searchResults.length === 0 && !this.isLoading && this.searchKey.length >= 2;
    }

    searchUsers(input) {
        this.isLoading = true;
        findUsers({ searchKey: input })
            .then(result => {
                this.error = null;
                console.log('Search results:', JSON.stringify(result));
                this.searchResults = result.map(user => {
                    return { ...user, ProfileName: user.Profile?.Name };
                });
                this.showTable = true;
                this.isLoading = false;
                this.currentlySelectedData = this.selectedData.map(row => row.Id);
            })
            .catch(error => {
                this.error = error;
                this.dispatchEvent(
                    new ShowToastEvent({
                        title: 'Error searching users',
                        message: error.body.message,
                        variant: 'error',
                    }),
                );
                this.isLoading = false;
            });
    }

    handleClear() {
        console.log('Clear search key');
    }

    handleRemovePill(event) {
        try {            
            console.log('event detail:', JSON.stringify(event.detail));
            const sfid = event.detail.name;
            console.log('Pill name:', sfid);
            this.selectedData = this.selectedData.filter((row) => {
                return row.Id !== sfid;
            });
            this.currentlySelectedData = this.selectedData.map(row => row.Id);
            this.refreshViews();
        } catch (error) {
            this.error = error.body.message;
        }
    }

    refreshViews() {
        this.selectedUsers = this.selectedData;
        const attributeChangeEvent = new FlowAttributeChangeEvent('selectedUsers', this.selectedUsers);
        //const currentlySelectedDataChangeEvent = new FlowAttributeChangeEvent('currentlySelectedData', this.currentlySelectedData);
        this.dispatchEvent(attributeChangeEvent);
        //this.dispatchEvent(currentlySelectedDataChangeEvent);
    }
}