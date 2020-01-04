// const host = 'http://127.0.0.1:5000/';
const host = window.location.protocol + '//' +
    window.location.hostname +
    (window.location.port ? ':' + window.location.port + '/' : '/');

const IMAGES_PER_PAGE = 50;

export { host, IMAGES_PER_PAGE };
