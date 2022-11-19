$(document).ready(function () {
    'use strict'

    let uuid = custom.getQueryParam('uuid')
    let toast = new custom.Toast($('#toast'))
    let info = $('#info')
    let file

    $.get(_urls.apiFile, {uuid: uuid}, function (res) {
        if (res.length !== 0) {
            file = res[0]
            file.type = file.file_type.substring(1)
            setInfo()

            for (const [key, formats] of Object.entries(_config.media)) {
                if (formats.indexOf(file.type) !== -1) {
                    if (file.file_size > _config.preview[key]) {
                        $('#notPermission').removeClass('d-none').find('.btn-info').click(function () {
                            location.href = _urls.fileBlob(uuid)
                        })
                    } else {
                        $.ajax(_urls.fileBlob(uuid), {
                            method: 'GET',
                            data: {blob: true},
                            xhrFields: {responseType: 'blob'},
                            beforeSend: function () {
                                toast.setText('Загрузка ресурсов')
                                toast.setIcon('fas fa-info-circle text-info')
                                toast.getToast().show()
                            },
                            success: function (blob) {
                                file.blobURL = URL.createObjectURL(blob)
                                switch (key) {
                                    case "video":
                                        videoPlayer()
                                        break
                                    case "audio":
                                        info.find('#tip').text('Перетаскивание тайминга воспроизведения звука в настоящее время не поддерживается')
                                        audioPlayer()
                                        break
                                    case "image":
                                        imageDisplay()
                                        break
                                }
                                toast.setText('Загрузка завершена')
                                toast.setIcon('fas fa-info-circle text-info')
                                toast.getToast().show()
                            }
                        })
                    }
                    return
                }
            }
            $('#notSupport').removeClass('d-none').find('.btn-info').click(function () {
                location.href = _urls.fileBlob(uuid)
            })
        }
    })

    // Воспроизведение видео
    function videoPlayer() {
        $('#videoPlayer').show()

        let player = videojs('videoPlayer', {
            loop: false,
            autoplay: false,
            controls: true,
            language: 'ru-RU',
            sources: [{
                src: file.blobURL,
                type: `video/${file.type}`
            }]
        })

        player.on('error', function () {
            toast.setText('Загрузка не удалась')
            toast.setIcon('fas fa-exclamation-circle text-danger')
            toast.getToast().show()
        })
    }

    // Воспроизведение звука
    function audioPlayer() {
        let elem = $('#audioPlayer').removeClass('d-none')
        let timer = elem.find('#timer span:nth-child(1)')
        let play = elem.find('#play')
        let progress = elem.find('#progress')

        let howl = new Howl({
            src: file.blobURL,
            volume: 0.3,
            format: [file.type],
            onplay: function () {
                requestAnimationFrame(step)
            },
            onend: function () {
                play.attr('class', 'fas fa-pause')
            },
            onloaderror: function () {
                toast.setText('Загрузка не удалась')
                toast.setIcon('fas fa-exclamation-circle text-danger')
                toast.getToast().show()
            },
            onplayerror: function () {
                toast.setText('Воспроизведение не удалось')
                toast.setIcon('fas fa-exclamation-circle text-danger')
                toast.getToast().show()
            }
        })

        // Инициализировать привязку
        howl.once('load', function () {
            elem.find('#timer span:nth-child(2)').text(timeFormat(howl.duration()))

            play.on('click', function () {
                $(this).toggleClass('fa-play fa-pause')
                howl.playing() ? howl.pause() : howl.play();
            })

            elem.find('#volume').on('input', function () {
                let value = this.value
                let icon = elem.find('#icon')
                if (value === '0') {
                    icon.attr('class', 'fas fa-volume-off')
                } else if (value > 0 && value <= 80) {
                    icon.attr('class', 'fas fa-volume-down')
                } else {
                    icon.attr('class', 'fas fa-volume-up')
                }
                howl.volume(this.value / 100)
            })
        })

        // Формат времени
        function timeFormat(seconds) {
            let min = 0
            let sec
            if (seconds > 60) {
                min = Math.floor(seconds / 60)
                sec = Math.floor(seconds % 60)
            } else {
                sec = Math.floor(seconds)
            }
            if (sec < 10) {
                sec = '0' + sec
            }
            return min + ":" + sec
        }

        // Анимация кадра
        function step() {
            progress.css('width', howl.seek() / howl.duration() * 100 + '%')
            timer.text(timeFormat(howl.seek()))
            if (howl.playing()) {
                requestAnimationFrame(step)
            }
        }
    }

    // картинка
    function imageDisplay() {
        $('#image').attr('src', file.blobURL).parent().removeClass('d-none')
    }

    // Установить информацию о файле
    function setInfo() {
        info.find('p:nth-child(1)').append(file.file_name)
        info.find('p:nth-child(2)').append(file.type)
        info.find('p:nth-child(3)').append(custom.fileSizeFormat(file.file_size))
        info.find('p:nth-child(4)').append(file.create_time)
    }
})