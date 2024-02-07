from __future__ import print_function
import argparse
import os
import re
import boto3
import argparse
from pydantic import BaseModel, Field

class CleanupConfig(BaseModel):
    dryrun: bool = Field(default=True, description='Prints the repository to be deleted without deleting them')
    imagestokeep: int = Field(default=100, description='Number of image tags to keep')
    region: str = Field(default='us-east-1', description='ECR region')
    ignoretagsregex: str = Field(default="^$", description='Regex of tag names to ignore')
    runningimagesfile: str = Field(default='complete.list', description='File containing the list of running images', required=True)

config = CleanupConfig()

parser = argparse.ArgumentParser(description='ECR Cleanup Script')
parser.add_argument('--runningimagesfile', type=str, required=True, help='File containing the list of running images')
parser.add_argument('--dryrun', type=bool, default=True, help='Prints the repository to be deleted without deleting them')

args = parser.parse_args()


def discover_delete_images():
    print("Discovering images in " + config.region)
    ecr_client = boto3.client('ecr', region_name=config.region)

    repositories = []
    describe_repo_paginator = ecr_client.get_paginator('describe_repositories')
    for response_listrepopaginator in describe_repo_paginator.paginate():
        for repo in response_listrepopaginator['repositories']:
            repositories.append(repo)

    # Read the list of running images from the file
    running_containers = []
    with open(config.runningimagesfile, 'r') as file:
        for line in file:
            running_containers.append(line.strip())

    print("Images that are running from the file:")
    for image in running_containers:
        print(image)

    for repository in repositories:
        print("------------------------")
        print("Starting with repository :" + repository['repositoryUri'])
        deletesha = []
        deletetag = []
        tagged_images = []

        describeimage_paginator = ecr_client.get_paginator('describe_images')
        for response_describeimagepaginator in describeimage_paginator.paginate(
                registryId=repository['registryId'],
                repositoryName=repository['repositoryName']):
            for image in response_describeimagepaginator['imageDetails']:
                if 'imageTags' in image:
                    tagged_images.append(image)
                else:
                    append_to_list(deletesha, image['imageDigest'])

        print("Total number of images found: {}".format(len(tagged_images) + len(deletesha)))
        print("Number of untagged images found {}".format(len(deletesha)))

        tagged_images.sort(key=lambda k: k['imagePushedAt'], reverse=True)

        # Get ImageDigest from ImageURL for running images. Do this for every repository
        running_sha = []
        for image in tagged_images:
            for tag in image['imageTags']:
                imageurl = repository['repositoryUri'] + ":" + tag
                for runningimages in running_containers:
                    if imageurl == runningimages:
                        if imageurl not in running_sha:
                            running_sha.append(image['imageDigest'])

        print("Number of running images found {}".format(len(running_sha)))
        ignore_tags_regex = re.compile(config.ignoretagsregex)
        for image in tagged_images:
            if tagged_images.index(image) >= config.imagestokeep:
                for tag in image['imageTags']:
                    if "latest" not in tag and ignore_tags_regex.search(tag) is None:
                        if not running_sha or image['imageDigest'] not in running_sha:
                            append_to_list(deletesha, image['imageDigest'])
                            append_to_tag_list(deletetag, {"imageUrl": repository['repositoryUri'] + ":" + tag,
                                                           "pushedAt": image["imagePushedAt"]})
        if deletesha:
            print("Number of images to be deleted: {}".format(len(deletesha)))
            delete_images(
                ecr_client,
                deletesha,
                deletetag,
                repository['registryId'],
                repository['repositoryName']
            )
        else:
            print("Nothing to delete in repository : " + repository['repositoryName'])


def append_to_list(image_digest_list, repo_id):
    if not {'imageDigest': repo_id} in image_digest_list:
        image_digest_list.append({'imageDigest': repo_id})


def append_to_tag_list(tag_list, tag_id):
    if not tag_id in tag_list:
        tag_list.append(tag_id)


def chunks(repo_list, chunk_size):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(repo_list), chunk_size):
        yield repo_list[i:i + chunk_size]


def delete_images(ecr_client, deletesha, deletetag, repo_id, name):
    if len(deletesha) >= 1:
        ## spliting list of images to delete on chunks with 100 images each
        ## http://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_BatchDeleteImage.html#API_BatchDeleteImage_RequestSyntax
        i = 0
        for deletesha_chunk in chunks(deletesha, 100):
            i += 1
            if not config.dryrun:
                delete_response = ecr_client.batch_delete_image(
                    registryId=repo_id,
                    repositoryName=name,
                    imageIds=deletesha_chunk
                )
                print(delete_response)
            else:
                print("registryId:" + repo_id)
                print("repositoryName:" + name)
                print("Deleting {} chank of images".format(i))
                print("imageIds:", end='')
                print(deletesha_chunk)
    if deletetag:
        print("Image URLs that are marked for deletion:")
        for ids in deletetag:
            print("- {} - {}".format(ids["imageUrl"], ids["pushedAt"]))


if __name__ == '__main__':
    discover_delete_images()
