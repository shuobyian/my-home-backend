import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { ReadMaterialDto } from 'src/material/dto/read-material-dto';
import { Material } from 'src/material/entities/material.entity';
import { UpdateProductDto } from 'src/product/dto/update-product-dto';
import { Item } from 'src/product/type/Item';
import { DataSource, Repository } from 'typeorm';

@Injectable()
export class MaterialService {
  constructor(
    private dataSource: DataSource,
    @InjectRepository(Material) private readonly material: Repository<Material>,
  ) {}

  create(material: Item['materials'][0], product_id: number) {
    return this.material.save(
      this.material.create({ product_id, ...material }),
    );
  }

  async createItem(item: Item, products: UpdateProductDto[]) {
    const findProduct = products.find((product) => product.name === item.name);

    return Promise.all(
      item.materials.map((material) => this.create(material, findProduct.id)),
    );
  }

  async createAll(items: Item[], products: UpdateProductDto[]) {
    return (
      await Promise.all(items.map((item) => this.createItem(item, products)))
    ).flat();
  }

  delete(product_id: number) {
    return this.material.delete({ product_id });
  }

  update(material: ReadMaterialDto) {
    return this.material.save(material);
  }
}
