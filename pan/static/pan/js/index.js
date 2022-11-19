$(document).ready(function () {
    'use strict'

    let loginBlock = $('#loginBlock')
    let registerBlock = $('#registerBlock')

    let next = custom.getQueryParam('next')
    let toast = new custom.Toast($('#toast'))

    if (next) {
        $('html').animate({
            scrollTop: loginBlock.offset().top - 48
        })
    }

    // скользить
    $('#loginLink').click(function () {
        $('html').animate({
            scrollTop: loginBlock.offset().top - 48
        })
    })

    $('#registerLink').click(function () {
        $('html').animate({
            scrollTop: registerBlock.offset().top
        })
    })


    /* Проверка входа в систему */
    let $loginForm = $('#loginForm')
    let loginForm = $loginForm.get(0)

    // Запишите первоначальную проверочную информацию
    let loginInputs = $loginForm.find('input')
    let loginValidations = custom.getInitial(loginInputs)

    // проверить подлинность
    $loginForm.find('#loginBtn').click(function () {
        if (!loginForm.checkValidity()) {
            custom.setInitial(loginValidations, loginInputs, $loginForm)
        } else {
            loginInputs.removeClass('is-invalid')
            let formData = $loginForm.serialize()

            $.post(_urls.login, formData, function (res) {
                if (res.code === 200) {
                    $.each(res.data, function (key, value) {
                        localStorage.setItem(key, value)
                    })

                    $('html').animate({
                        scrollTop: $(document.body).offset().top,
                    }, {
                        start: function () {
                            toast.setText(res.msg)
                            toast.getToast().show()
                        },
                        done: function () {
                            setTimeout(function () {
                                if (next) {
                                    location.replace(_domain + next)
                                } else {
                                    location.replace(_domain)
                                }
                            }, 400)
                        }
                    })
                } else {
                    let errors = res.data.errors
                    $.each(errors, function (key) {
                        loginValidations[key].elem.text(errors[key][0])
                        $loginForm.find(`input[name=${key}]`).addClass('is-invalid')
                    })
                }
            })
            $loginForm.removeClass('was-validated')
        }
    })


    /* Проверка регистрации */
    let $registerForm = $('#registerForm')
    let registerForm = $registerForm.get(0)

    // Запишите первоначальную проверочную информацию
    let registerInputs = $registerForm.find('input')
    let registerValidations = custom.getInitial(registerInputs)

    // проверять подлинность
    $registerForm.find('#registerBtn').click(function () {
        if (!registerForm.checkValidity()) {
            custom.setInitial(registerValidations, registerInputs, $registerForm)
        } else {
            registerInputs.removeClass('is-invalid')
            if (custom.checkPassword($('#registerPassword'), $('#confirmPassword'))) {
                let formData = $registerForm.serialize()

                $.post(_urls.register, formData, function (res) {
                    if (res.code === 200) {
                        $('html').animate({
                            scrollTop: loginBlock.offset().top - 48,
                        }, {
                            start: function () {
                                toast.setText(res.msg)
                                toast.getToast().show()
                            },
                        })
                    } else {
                        let errors = res.data.errors
                        $.each(errors, function (key) {
                            registerValidations[key].elem.text(errors[key][0])
                            $registerForm.find(`input[name=${key}]`).addClass('is-invalid')
                        })
                    }
                })
            }
            $registerForm.removeClass('was-validated')
        }
    })


    // Сброс пароля
    let $resetForm = $('#resetForm')
    let resetForm = $resetForm.get(0)

    let resetInputs = $resetForm.find('input')
    let resetValidations = custom.getInitial(resetInputs)

    let $resetBtn = $('#resetBtn')

    $resetBtn.click(function () {
        if (!resetForm.checkValidity()) {
            custom.setInitial(registerValidations, registerInputs, $resetForm)
        } else {
            $resetBtn.prop('disabled', true)
            resetInputs.removeClass('is-invalid')
            let formData = $resetForm.serialize()

            $.post(_urls.reset, formData, function (res) {
                if (res.code === 200) {
                    let age = 60
                    let timer = setInterval(function () {
                        if (age === 0) {
                            clearInterval(timer)
                            $resetBtn.text('подтвердить')
                            $resetBtn.prop('disabled', false)
                        }
                        $resetBtn.text(age)
                        age--
                    }, 1000)

                    toast.setText(res.msg)
                    toast.getToast().show()
                } else {
                    let errors = res.data.errors
                    $.each(errors, function (key) {
                        resetValidations[key].elem.text(errors[key][0])
                        $resetForm.find(`input[name=${key}]`).addClass('is-invalid')
                    })
                    $resetBtn.prop('disabled', false)
                }
            })
            $resetForm.removeClass('was-validated')
        }
    })


    // enter
    $.each($('form'), function (i, item) {
        let form = $(item)
        let btn = form.find('button')

        form.find('input').on('keypress', function (e) {
            if (e.which === 13) {
                btn.click()
            }
        })
    })


    // Получить общие файлы
    let cloudBlock = $('#cloudBlock')
    let btnToggle = cloudBlock.find('#btnToggle')
    let inputToggle = cloudBlock.find('#inputToggle')
    let shareCard = cloudBlock.find('#shareCard')
    let btn = shareCard.find('.btn-info')

    btnToggle.find('#receiveBtn').click(function () {
        btnToggle.toggle('normal')
        inputToggle.toggle('normal', function () {
            inputToggle.find('#shareKey').val('')
        })
    })

    inputToggle.find('#closeIcon').click(function () {
        btnToggle.toggle('normal')
        inputToggle.toggle('normal', function () {
            inputToggle.find('#shareKey').val('')
        })
    })

    shareCard.find('.icon-link').click(function () {
        inputToggle.toggle('normal', function () {
            inputToggle.find('#shareKey').val('')
        })
        shareCard.toggle('normal', function () {
            btn.off('click')
        })
    })

    // Получить общие файлы
    $('#shareKey').on('input', function () {
        if (this.value.length === 6) {
            $.post(_urls.shareGet, {key: this.value}, function (res) {
                if (res.code === 200) {
                    let file = res.data.file
                    let share = res.data.share
                    shareCard.find('.file-title').text(file.name)
                    shareCard.find('#summary').text(share.summary)
                    shareCard.find('#expire').text(custom.humanizeTime(share.expire))
                    shareCard.find('#fileSize').text(custom.fileSizeFormat(file.size))
                    shareCard.toggle('normal', function () {
                        btn.click(function () {
                            toast.setIcon('fas fa-info-circle text-info')
                            toast.setText('пожалуйста, подождите минутку')
                            toast.getToast().show()
                            location.href = _urls.fileBlob(file.uuid)
                        })
                    })
                    inputToggle.toggle('normal')
                } else {
                    toast.setIcon('fas fa-exclamation-circle text-warning')
                    toast.setText(res.msg)
                    toast.getToast().show()
                }
            })
        }
    })
})