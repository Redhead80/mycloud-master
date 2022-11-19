$(document).ready(function () {
    'use strict'

    let historyTable = $('#historyTable')

    let alert = new custom.Alert($('#alert'))
    let toast = new custom.Toast($('#toast'))
    let modal = new custom.Modal($('#modal'))
    let baseModal = new custom.BaseModal($('#shareModal'))

    baseModal.elem.on('hidden.mdb.modal', function () {
        baseModal.elem.find('#delta').text('Пожалуйста выберите')
    })

    historyTable.bootstrapTable({
        url: _urls.apiHistory,
        dataField: 'results',
        totalField: 'count',
        sidePagination: 'server',
        classes: 'table table-hover',
        toolbar: '#toolbar',
        clickToSelect: true,
        pagination: true,
        pageSize: 8,
        paginationHAlign: 'end',
        paginationParts: ['pageList'],
        queryParamsType: 'limit',
        loadingTemplate: table.loadingTemplate,
        formatNoMatches: function () {
            return 'Нет истории передачи';
        },
        columns: [{
            checkbox: true,
        }, {
            field: 'user_file',
            title: 'Имя файла',
            formatter: table.fileNameFormatter,
        }, {
            field: 'create_time',
            title: 'Время создания',
        }, {
            field: 'expire_time',
            title: 'Срок годности',
            formatter: custom.humanizeTime,
        }, {
            clickToSelect: false,
            formatter: actionsFormatter,
        }],
    });

    table.tableSort(historyTable)
    table.tableOrder(historyTable)
    table.tableSearch(historyTable)

    $('#delBtn').click(function () {
        let checks = historyTable.bootstrapTable('getSelections')

        if (checks.length === 0) {
            toast.setIcon('fas fa-exclamation-circle text-warning')
            toast.setText('Запись не выбрана')
            toast.getToast().show()
        } else {
            modal.setTitle("Вы уверены, что хотите удалить выбранную запись")
            modal.setBtnType("btn btn-danger")

            function del() {
                let ids = checks.map(function (item) {
                    return item.id
                })
                table.alterCallback(_urls.shareDelete, {ids: ids}, toast, historyTable)
                modal.getModal().hide()
            }

            modal.elem.one('show.mdb.modal', function () {
                modal.btn.on('click', del)
            }).one('hide.mdb.modal', function () {
                modal.btn.off('click', del)
            })
            modal.getModal().show()
        }
    })

    historyTable.on('post-body.bs.table', function () {
        $('.custom-link').each(function (i, elem) {
            let id = elem.dataset.customId
            let index = elem.dataset.customIndex
            let func = null

            switch (elem.dataset.customMethod) {
                case "copy":
                    func = function () {
                        linkCopy(index)
                    }
                    break
                case "setting":
                    func = function () {
                        shareSetting(index)
                    }
                    break
                case "del":
                    func = function () {
                        shareDel(id)
                    }
                    break
            }
            elem.addEventListener('click', func)
        })
    })

    /**
     * Функция настройки таблицы
     */
    function actionsFormatter(value, row, index) {
        return `<div class="d-flex flex-column flex-md-row align-items-center">
                    <a class="icon-link custom-link" href="javascript:void(0)" data-custom-id="${row.id}" 
                       data-custom-index="${index}" data-custom-method="copy">
                        <i class="fas fa-link"></i>
                    </a>
                    <a class="ms-md-3 icon-link dropdown-toggle hidden-arrow" href="javascript:void(0)"
                            data-mdb-toggle="dropdown">
                        <i class="fas fa-ellipsis-v"></i>
                    </a>
                    <ul class="dropdown-menu">
                        <li><a class="dropdown-item custom-link icon-link" data-custom-method="setting" 
                                data-custom-index="${index}" data-custom-id="${row.id}" 
                                href="javascript:void(0)"><i class="fas fa-cog me-2"></i>Установить ссылку</a></li>
                        <li><a class="dropdown-item custom-link icon-link" data-custom-method="del" 
                                data-custom-index="${index}" data-custom-id="${row.id}" 
                                href="javascript:void(0)"><i class="fas fa-trash me-2"></i>стереть</a></li>
                    </ul>
                </div>`
    }

    /**
     * Операция обмена файлами
     */
    function linkCopy(index) {
        let data = historyTable.bootstrapTable('getData', {includeHiddenRows: true})[index]
        custom.copyText(`файл: ${data.user_file}\n` +
            `Общий доступ к паролю: ${data.secret_key}\n` +
            `Обмен ссылками: ${_urls.share(data.signature)}`, alert)
    }

    function shareDel(id) {
        modal.setTitle("Вы уверены, что хотите удалить запись")
        modal.setBtnType("btn btn-danger")

        function del() {
            table.alterCallback(_urls.shareDelete, {ids: [id]}, toast, historyTable)
            modal.getModal().hide()
        }

        modal.elem.one('show.mdb.modal', function () {
            modal.btn.on('click', del)
        }).one('hide.mdb.modal', function () {
            modal.btn.off('click', del)
        })
        modal.getModal().show()
    }

    function shareSetting(index) {
        let $elem = baseModal.elem
        let $mask = $elem.find('.copy-mask')
        let $delta = $elem.find('#delta')
        let $deltas = $elem.find('.dropdown-item')
        let $summary = $elem.find('#summary')
        let $copyBtn = $elem.find('.btn-info')

        let data = historyTable.bootstrapTable('getData', {includeHiddenRows: true})[index]
        let deltaChange = false
        let summaryChange = false

        // Получите ключ для заполнения
        $elem.find('#shareLink').text(_urls.share(data.signature))
        $elem.find('#shareKey').text(data.secret_key)

        $elem.one('show.mdb.modal', function () {
            $mask.on('click', function () {
                custom.copyText(this.previousElementSibling.textContent, alert)
            })
            $copyBtn.on('click', function () {
                custom.copyText(`файл: ${data.user_file}\n` +
                    `Общий доступ к паролю: ${data.secret_key}\n` +
                    `Обмен ссылками: ${_urls.share(data.signature)}`, alert)
            })
            $deltas.on('click', function () {
                deltaChange = true
                $delta.data('customDelta', Number(this.dataset.customDelta)).text(this.textContent)
            })
            $summary.on('change', function () {
                summaryChange = true
            })
        }).one('hide.mdb.modal', function () {
            $mask.off('click')
            $copyBtn.off('click')
            $deltas.off('click')
            $summary.off('change')
            if (deltaChange || summaryChange) {
                table.alterCallback(_urls.shareUpdate, {
                    id: data.id,
                    delta: deltaChange ? Number($delta.data('customDelta')) : undefined,
                    summary: summaryChange ? $summary.val() : undefined
                }, toast, historyTable)
            }
        })
        baseModal.mdbModal.show()
    }
})