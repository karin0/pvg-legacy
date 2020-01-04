import React, { useState, Component } from 'react';

import { Link, Chip, Grid, Typography } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';

import Pagination from "material-ui-flat-pagination";
import Carousel, { Modal, ModalGateway } from 'react-images';
import Gallery from 'react-photo-gallery';

import { host, IMAGES_PER_PAGE } from './env.js';

const useStyles = makeStyles({
    mr: {
        marginRight: '0.5em'
    },
    md: {
        marginDown: '1em'
    }
});

function ImageCaption(props) {
    const classes = useStyles();

    const img = props.img;
    const illust_url = 'https://www.pixiv.net/artworks/' + img.pid.toString(),
          author_url = 'https://www.pixiv.net/member.php?id=' + img.aid.toString();

    return (
        <Typography>
            <div className={classes.md}>
                <Link href={illust_url} className={classes.mr}>{img.title}</Link>
                <Link href={author_url}>{img.author}</Link>
            </div>
            {img.tags.map(tag =>
                <Chip
                    className={classes.mr}
                    label={tag}
                    onClick={ () => {
                        props.update_tags(tag, img.nav);
                    }}
                />
            )}
        </Typography>
    );
}

function GalleryView(props) {
    const [index, set_index] = useState(-1);

    return (
        <>
            <Gallery photos={props.images} onClick={ (e, {index}) => set_index(index) } />
            <ModalGateway>
                {index >= 0 ? (
                <Modal onClose={ () => set_index(-1) }>
                    <Carousel
                        currentIndex={index}
                        views={props.views}
                    />
                </Modal>
                ) : null}
            </ModalGateway>
        </>
    );
}

class GalleryPagination extends Component {
    state = {
        offset: this.props.default_offset,
    };

    set_offset = off => {
        this.setState({
            offset: off
        });
    };

    render() {
        const off = this.state.offset, pages = this.props.pages, tot = pages.length;

        let images, views;
        if (off < tot) {
            images = pages[off];
            views = this.props.modal_pages[off];
        } else
            images = views = [];

        return (
            <>
                <Grid container justify="center">
                    <Pagination
                        limit={1}
                        offset={off}
                        total={tot}
                        onClick={(e, offset) => this.set_offset(offset)}
                        otherPageColor="default"
                    />
                </Grid>
                <GalleryView
                    images={images}
                    views={views}
                />
            </>
        );
    }
}


export default function PvgGallery(props) {
    let pages = [], modal_pages = [], page = [], modal_page = [], offset = 0;

    for (const img of props.images) {
        if (img.nav === props.locating_id)
            offset = pages.length;

        const src = host + 'img/' + img.nav;
        page.push({
            src,
            width: img.w,
            height: img.h
        });
        modal_page.push({
            source: src,
            caption: <ImageCaption img={img} update_tags={props.update_tags} />
        });

        if (page.length >= IMAGES_PER_PAGE) {
            pages.push(page);
            modal_pages.push(modal_page);
            page = [];
            modal_page = [];
        }
    }
    if (page.length) {
        pages.push(page);
        modal_pages.push(modal_page);
    }

    return (
        <GalleryPagination
            pages={pages}
            modal_pages={modal_pages}
            default_offset={offset}
            key={Date.now()} // anti-pattern?
        />
    );
}
